// Compile the legacy C account store (csrc/acct.c) and link it in. No external
// crates: just the system C compiler and ar.
use std::env;
use std::path::Path;
use std::process::Command;

fn main() {
    let out = env::var("OUT_DIR").unwrap();
    let obj = Path::new(&out).join("acct.o");
    let lib = Path::new(&out).join("libacct.a");
    let cc = env::var("CC").unwrap_or_else(|_| "cc".into());

    let ok = Command::new(&cc)
        .args(["-c", "-O2", "-fPIC", "-Wall", "csrc/acct.c", "-o"])
        .arg(&obj)
        .status()
        .expect("failed to run the C compiler")
        .success();
    assert!(ok, "compiling csrc/acct.c failed");

    let ok = Command::new("ar")
        .arg("crus")
        .arg(&lib)
        .arg(&obj)
        .status()
        .expect("failed to run ar")
        .success();
    assert!(ok, "archiving libacct.a failed");

    println!("cargo:rustc-link-search=native={out}");
    println!("cargo:rustc-link-lib=static=acct");
    println!("cargo:rerun-if-changed=csrc/acct.c");
}
