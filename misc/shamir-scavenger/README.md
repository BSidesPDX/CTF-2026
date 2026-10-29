# 2026 Shamir Secret Share Scavenger Hunt

```md
There is more to the conference than the CTF, and we want to encourage you to explore as much of it as possible. There are Shamir Secret Shares to collect throughout the conference.

**What you know about this challenge:**

1. The Shamir Secret Sharing(SSS) algorithm (there's code online for it)
2. You will have until the end of the CTF to submit the flag, but you'll want to collect as many shares as early as you can; not every secret share will be available both days.
3. Some keys are only available at certain locations or at certain events. Others might be found through general socializing in the hallway.
4. There are duplicates of each key.
5. That there are 13 total keys. Typically this is the variable 'n' in the algorithm.
6. You'll need to wrap the secret in the flag format `pdx{...}` when you submit it. It will not be in the flag itself.
7. The flag is an ascii string of a short recognizable leetspeak phrase.
    In playtesting we saw some instability with the final 2 characters. You might have to run the math a few times if you are at the minimum number of keys.
    - If you are seeing something else, the math is off somewhere or you don't have enough shares yet.
    - You might need to re-run your script if you have the minimum number of shares. Sometimes the reconstructed secret approximately is slightly too far off the original. Collecting more shares produces more stable results.
8. There's more to BSidesPDX than the CTF.

**What you don't know about this challenge:**

1. What the minimum number of shares are is. Typically this is the variable 'm' in the algorithm.
2. Who the key carriers are. Some may advertise themselves, others may not.
    - Key carriers are free to set their own reasonable rules for earning the key, such as a minimum amount of small talk, staying until the end of a talk, that you must tell them an interesting story, etc.
3. How long any secret shares will be available during the conference or how many duplicates there are of each key.
```

Points: 500..100, dynamic

Author: CTF Committee

## Walkthrough

Find at least 8 keys and perform the Shamir Secret Sharing algorithm to reconstruct the flag.

## Flag

`pdx{Soci4lFl4g}`
