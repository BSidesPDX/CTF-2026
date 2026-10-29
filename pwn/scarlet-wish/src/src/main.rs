//! acctd: a small account server.
//!
//! The network protocol and the login checks are handled here in Rust; the
//! per-user files live in a legacy C store (see csrc/acct.c).
//!
//! Wire protocol, all lengths big-endian u16:
//!   request:  [u8 opcode][field...]   field = [u16 len][len bytes]
//!   response: [u8 status][u16 len][len bytes]   status 0 = ok, 1 = error
//!
//!   1 REGISTER  user, pass      -> "registered"
//!   2 LOGIN     user, pass      -> 16-byte session token
//!   3 WHOAMI    token           -> the session's username
//!   4 LISTUSERS                 -> the store's account names, one per line
//!   5 LISTFILES token           -> the user's file names, one per line
//!   6 READFILE  token, name     -> the file's contents
//!   7 WRITEFILE token, name, data -> saves the file (if the store is writable)

use std::collections::HashMap;
use std::ffi::{c_char, c_int, c_long, CStr};
use std::fs::File;
use std::io::{self, Read, Write};
use std::os::unix::ffi::OsStrExt;
use std::sync::OnceLock;

extern "C" {
    fn acct_base() -> *const c_char;
    fn acct_users(out: *mut c_char, out_len: usize) -> c_long;
    fn acct_list(user: *const c_char, out: *mut c_char, out_len: usize) -> c_long;
    fn acct_read(
        user: *const c_char,
        name: *const c_char,
        out: *mut c_char,
        out_len: usize,
    ) -> c_long;
    fn acct_write(
        user: *const c_char,
        name: *const c_char,
        data: *const c_char,
        len: usize,
    ) -> c_int;
    fn acct_strerror(err: c_int) -> *const c_char;
}

const MAX_FIELD: usize = 4096;
const OUT_LEN: usize = 4096;

/// The connect banner
const GREETING: &[u8] = b"\
    Westview Public Library  --  Patron Services\n\
    Welcome to Westview! We're so glad you moved in.\n\
    \n\
    New in town? The guest card is on the desk: LOGIN guest / guest.\n\
    Everything is fine here.";

fn urandom(n: usize) -> Vec<u8> {
    let mut f = File::open("/dev/urandom").expect("open /dev/urandom");
    let mut b = vec![0u8; n];
    f.read_exact(&mut b).expect("read /dev/urandom");
    b
}

/// Read exactly `buf.len()` bytes, or return false on a clean EOF or error.
fn fill<R: Read>(r: &mut R, buf: &mut [u8]) -> bool {
    let mut off = 0;
    while off < buf.len() {
        match r.read(&mut buf[off..]) {
            Ok(0) => return false,
            Ok(n) => off += n,
            Err(ref e) if e.kind() == io::ErrorKind::Interrupted => {}
            Err(_) => return false,
        }
    }
    true
}

fn read_op<R: Read>(r: &mut R) -> Option<u8> {
    let mut b = [0u8; 1];
    fill(r, &mut b).then_some(b[0])
}

/// Load file contents.
fn read_field<R: Read>(r: &mut R) -> Option<Vec<u8>> {
    let mut len = [0u8; 2];
    if !fill(r, &mut len) {
        return None;
    }
    let len = u16::from_be_bytes(len) as usize;
    if len > MAX_FIELD {
        return None;
    }
    let mut v = vec![0u8; len];
    fill(r, &mut v).then_some(v)
}

/// Store file contents.
fn respond<W: Write>(w: &mut W, status: u8, body: &[u8]) -> io::Result<()> {
    let len = body.len().min(u16::MAX as usize);
    w.write_all(&[status])?;
    w.write_all(&(len as u16).to_be_bytes())?;
    w.write_all(&body[..len])?;
    w.flush()
}

/// Make a C string for the legacy store, whose functions take `char *`.
fn c_name(bytes: &[u8]) -> Vec<u8> {
    let mut buf = Vec::with_capacity(bytes.len() + 1);
    buf.extend_from_slice(bytes);
    buf.push(0);
    buf
}

/// Render untrusted bytes for a log line: quoted, with control bytes escaped.
fn show(bytes: &[u8]) -> String {
    format!("{:?}", String::from_utf8_lossy(bytes))
}

/// Every log line is tagged with this process's id and the connecting client's
/// address, set once at startup, so a reader can group and filter a session's
/// lines.
static LOG_TAG: OnceLock<String> = OnceLock::new();

/// The address to log for this connection. A front end may record the client's
/// address in an environment variable named by `--peer-env NAME`; without the
/// option, or when the named variable is unset or empty, the address is "-".
fn peer_addr() -> String {
    let mut args = std::env::args().skip(1);
    let name = loop {
        match args.next() {
            Some(arg) => {
                if let Some(name) = arg.strip_prefix("--peer-env=") {
                    break Some(name.to_string());
                }
                if arg == "--peer-env" {
                    break args.next();
                }
            }
            None => break None,
        }
    };
    name.and_then(|name| std::env::var(name).ok())
        .filter(|addr| !addr.is_empty())
        .unwrap_or_else(|| "-".to_string())
}

/// Write one request line to the log on stderr, tagged with pid and address.
fn log(line: &str) {
    let tag = LOG_TAG.get().map(String::as_str).unwrap_or("- -");
    eprintln!("{tag} {line}");
}

/// A path component in a READFILE/WRITEFILE name: alphanumeric, 1-64 bytes.
fn is_alnum(bytes: &[u8]) -> bool {
    !bytes.is_empty() && bytes.len() <= 64 && bytes.iter().all(|&b| b.is_ascii_alphanumeric())
}

/// Does an account directory already exist for this name? Join the base and the
/// name as the store does, then stat the result.
fn account_dir_exists(user: &[u8]) -> bool {
    let base = unsafe { CStr::from_ptr(acct_base()) }.to_bytes();
    let mut path = Vec::with_capacity(base.len() + 1 + user.len());
    path.extend_from_slice(base);
    path.push(b'/');
    path.extend_from_slice(user);
    std::fs::metadata(std::ffi::OsStr::from_bytes(&path))
        .map(|m| m.is_dir())
        .unwrap_or(false)
}

/// Resolve a READFILE/WRITEFILE name to the (user, file) it names.
///
/// A bare `file` is the caller's own directory. A leading `/` means an explicit
/// `/user/file` and demands a second `/`. `.` is never allowed, and an explicit
/// user and file are alphanumeric.
fn resolve(
    name: &[u8],
    session_user: &[u8],
    write: bool,
) -> Result<(Vec<u8>, Vec<u8>), &'static str> {
    if name.contains(&b'.') {
        return Err("names may not contain '.'");
    }
    if name.first() == Some(&b'/') {
        let rest = &name[1..];
        let slash = match rest.iter().position(|&c| c == b'/') {
            Some(i) => i,
            None => return Err("a leading '/' needs the form /user/file"),
        };
        let user = &rest[..slash];
        let file = &rest[slash + 1..];
        if !is_alnum(user) || !is_alnum(file) {
            return Err("user and file must be 1-64 alphanumeric bytes");
        }
        if write && user != session_user {
            return Err("not your directory");
        }
        Ok((user.to_vec(), file.to_vec()))
    } else {
        if !is_alnum(name) {
            return Err("file must be 1-64 alphanumeric bytes");
        }
        Ok((session_user.to_vec(), name.to_vec()))
    }
}

fn main() {
    let _ = LOG_TAG.set(format!("{} {}", std::process::id(), peer_addr()));

    let stdin = io::stdin();
    let stdout = io::stdout();
    let mut r = stdin.lock();
    let mut w = stdout.lock();

    // username -> password, for the life of this connection.
    let mut accounts: HashMap<Vec<u8>, Vec<u8>> = HashMap::new();
    // token -> username.
    let mut sessions: HashMap<Vec<u8>, Vec<u8>> = HashMap::new();

    let _ = respond(&mut w, 0, GREETING);

    while let Some(op) = read_op(&mut r) {
        match op {
            // REGISTER user pass
            1 => {
                let (user, pass) = match (read_field(&mut r), read_field(&mut r)) {
                    (Some(u), Some(p)) => (u, p),
                    _ => break,
                };
                log(&format!("REGISTER user={}", show(&user)));
                if accounts.contains_key(&user) || account_dir_exists(&user) {
                    let _ = respond(&mut w, 1, b"username taken");
                    continue;
                }
                accounts.insert(user, pass);
                let _ = respond(&mut w, 0, b"registered");
            }
            // LOGIN user pass
            2 => {
                let (user, pass) = match (read_field(&mut r), read_field(&mut r)) {
                    (Some(u), Some(p)) => (u, p),
                    _ => break,
                };
                log(&format!("LOGIN user={}", show(&user)));
                let authed = match accounts.get(&user) {
                    // Registered this connection. TODO: sync to storage.
                    Some(stored) => *stored == pass,
                    // Otherwise an account may carry a "password" file in its
                    // store directory that authorizes a login.
                    None => {
                        let cuser = c_name(&user);
                        let cpass = c_name(b"password");
                        let mut out = vec![0u8; OUT_LEN];
                        let n = unsafe {
                            acct_read(
                                cuser.as_ptr() as *const c_char,
                                cpass.as_ptr() as *const c_char,
                                out.as_mut_ptr() as *mut c_char,
                                OUT_LEN,
                            )
                        };
                        n >= 0 && out[..n as usize] == pass[..]
                    }
                };
                if authed {
                    let token = urandom(16);
                    sessions.insert(token.clone(), user);
                    let _ = respond(&mut w, 0, &token);
                } else {
                    let _ = respond(&mut w, 1, b"bad credentials");
                }
            }
            // WHOAMI token
            3 => {
                let token = match read_field(&mut r) {
                    Some(t) => t,
                    None => break,
                };
                log("WHOAMI");
                match sessions.get(&token) {
                    Some(user) => {
                        let _ = respond(&mut w, 0, user);
                    }
                    None => {
                        let _ = respond(&mut w, 1, b"not logged in");
                    }
                }
            }
            // LISTUSERS
            4 => {
                log("LISTUSERS");
                let mut out = vec![0u8; OUT_LEN];
                let n = unsafe { acct_users(out.as_mut_ptr() as *mut c_char, OUT_LEN) };
                if n < 0 {
                    let _ = respond(&mut w, 1, b"no accounts");
                } else {
                    let mut names: Vec<&[u8]> = out[..n as usize]
                        .split(|&b| b == b'\n')
                        .filter(|s| !s.is_empty())
                        .collect();
                    names.sort_unstable();
                    let mut body = Vec::new();
                    for name in names {
                        body.extend_from_slice(name);
                        body.push(b'\n');
                    }
                    let _ = respond(&mut w, 0, &body);
                }
            }
            // LISTFILES token
            5 => {
                let token = match read_field(&mut r) {
                    Some(t) => t,
                    None => break,
                };
                let user = match sessions.get(&token) {
                    Some(u) => u.clone(),
                    None => {
                        let _ = respond(&mut w, 1, b"not logged in");
                        continue;
                    }
                };
                log(&format!("LISTFILES user={}", show(&user)));
                let cuser = c_name(&user);
                let mut out = vec![0u8; OUT_LEN];
                let n = unsafe {
                    acct_list(
                        cuser.as_ptr() as *const c_char,
                        out.as_mut_ptr() as *mut c_char,
                        OUT_LEN,
                    )
                };
                if n < 0 {
                    let _ = respond(&mut w, 1, b"you own no files");
                } else {
                    let _ = respond(&mut w, 0, &out[..n as usize]);
                }
            }
            // READFILE token name
            6 => {
                let (token, name) = match (read_field(&mut r), read_field(&mut r)) {
                    (Some(t), Some(n)) => (t, n),
                    _ => break,
                };
                let user = match sessions.get(&token) {
                    Some(u) => u.clone(),
                    None => {
                        let _ = respond(&mut w, 1, b"not logged in");
                        continue;
                    }
                };
                log(&format!(
                    "READFILE user={} name={}",
                    show(&user),
                    show(&name)
                ));
                let (euser, file) = match resolve(&name, &user, true) {
                    Ok(pair) => pair,
                    Err(msg) => {
                        let _ = respond(&mut w, 1, msg.as_bytes());
                        continue;
                    }
                };
                let cuser = c_name(&euser);
                let cname = c_name(&file);
                let mut out = vec![0u8; OUT_LEN];
                let n = unsafe {
                    acct_read(
                        cuser.as_ptr() as *const c_char,
                        cname.as_ptr() as *const c_char,
                        out.as_mut_ptr() as *mut c_char,
                        OUT_LEN,
                    )
                };
                if n < 0 {
                    let _ = respond(&mut w, 1, b"no such file");
                } else {
                    let _ = respond(&mut w, 0, &out[..n as usize]);
                }
            }
            // WRITEFILE token name data
            7 => {
                let (token, name, data) =
                    match (read_field(&mut r), read_field(&mut r), read_field(&mut r)) {
                        (Some(t), Some(n), Some(d)) => (t, n, d),
                        _ => break,
                    };
                let user = match sessions.get(&token) {
                    Some(u) => u.clone(),
                    None => {
                        let _ = respond(&mut w, 1, b"not logged in");
                        continue;
                    }
                };
                log(&format!(
                    "WRITEFILE user={} name={} ({} bytes)",
                    show(&user),
                    show(&name),
                    data.len()
                ));
                let (euser, file) = match resolve(&name, &user, false) {
                    Ok(pair) => pair,
                    Err(msg) => {
                        let _ = respond(&mut w, 1, msg.as_bytes());
                        continue;
                    }
                };
                let cuser = c_name(&euser);
                let cname = c_name(&file);
                let rc = unsafe {
                    acct_write(
                        cuser.as_ptr() as *const c_char,
                        cname.as_ptr() as *const c_char,
                        data.as_ptr() as *const c_char,
                        data.len(),
                    )
                };
                if rc == 0 {
                    let _ = respond(&mut w, 0, b"saved");
                } else {
                    let why = unsafe { CStr::from_ptr(acct_strerror(rc)) }.to_bytes();
                    let _ = respond(&mut w, 1, why);
                }
            }
            _ => {
                log(&format!("unknown opcode {op}"));
                let _ = respond(&mut w, 1, b"unknown opcode");
            }
        }
    }
}
