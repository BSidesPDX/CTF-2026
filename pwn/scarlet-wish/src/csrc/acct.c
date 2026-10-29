/*
 * Legacy account store, from the old C server. Each user owns a directory of
 * files under ACCT_DIR (default /srv/acct), one directory per username:
 *
 *     /srv/acct/<user>/<file>
 *
 * ACCT_DIR can be overridden at run time, which the tests rely on.
 */
#include <dirent.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef ACCT_DIR
#define ACCT_DIR "/srv/acct"
#endif

static const char *acct_dir(void)
{
    const char *dir = getenv("ACCT_DIR");
    return dir ? dir : ACCT_DIR;
}

/* The store's base directory. */
const char *acct_base(void)
{
    return acct_dir();
}

/*
 * List the account directories (one per user) under the store, one name per
 * line into out. Returns bytes written, or -1 on error. The top level holds
 * one directory per account, so every entry is a user.
 */
long acct_users(char *out, size_t out_len)
{
    DIR *d = opendir(acct_dir());
    if (!d)
        return -1;

    size_t used = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (strcmp(e->d_name, ".") == 0 || strcmp(e->d_name, "..") == 0)
            continue;
        size_t l = strlen(e->d_name);
        if (used + l + 1 >= out_len)
            break;
        memcpy(out + used, e->d_name, l);
        used += l;
        out[used++] = '\n';
    }
    closedir(d);
    out[used] = '\0';
    return (long)used;
}

/*
 * List the files user owns, one name per line, into out.
 * Returns the number of bytes written, or -1 if the user has no directory.
 */
long acct_list(const char *user, char *out, size_t out_len)
{
    char path[512];
    int n = snprintf(path, sizeof(path), "%s/%s", acct_dir(), user);
    if (n < 0 || (size_t)n >= sizeof(path))
        return -1;

    DIR *d = opendir(path);
    if (!d)
        return -1;

    size_t used = 0;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (strcmp(e->d_name, ".") == 0 || strcmp(e->d_name, "..") == 0)
            continue;
        size_t l = strlen(e->d_name);
        if (used + l + 1 >= out_len)
            break;
        memcpy(out + used, e->d_name, l);
        used += l;
        out[used++] = '\n';
    }
    closedir(d);
    out[used] = '\0';
    return (long)used;
}

/*
 * Read one of user's files into out (up to out_len-1 bytes).
 * Returns the number of bytes read, or -1 on error.
 */
long acct_read(const char *user, const char *name, char *out, size_t out_len)
{
    char path[512];
    int n = snprintf(path, sizeof(path), "%s/%s/%s", acct_dir(), user, name);
    if (n < 0 || (size_t)n >= sizeof(path))
        return -1;

    FILE *f = fopen(path, "rb");
    if (!f)
        return -1;
    size_t r = fread(out, 1, out_len - 1, f);
    fclose(f);
    out[r] = '\0';
    return (long)r;
}

/*
 * Write data (len bytes) to one of user's files. Returns 0 on success, or the
 * errno from the attempt.
 */
int acct_write(const char *user, const char *name, const char *data, size_t len)
{
    char path[512];
    int n = snprintf(path, sizeof(path), "%s/%s/%s", acct_dir(), user, name);
    if (n < 0 || (size_t)n >= sizeof(path))
        return ENAMETOOLONG;

    FILE *f = fopen(path, "wb");
    if (!f)
        return errno;
    fwrite(data, 1, len, f);
    fclose(f);
    return 0;
}

/* Error report string. */
const char *acct_strerror(int err)
{
    return strerror(err);
}
