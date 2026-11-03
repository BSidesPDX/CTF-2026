# know-after

```md
Contoso Corporation just laid off a large portion of its security team, and word is that
basic hygiene is already slipping. Allegedly one of the executives keeps their password on a
Post-it under their keyboard. See what you can suss out.

[(971) 587-0986](tel:+19715870986)
```

Points: 500..100, dynamic

Author: Alex

## Walkthrough

The challenge was set up with a naive LLM with a number of personalities, and a decision model gating the call. The different personalities represent the different people (receptionist, executives, etc) in the office. The decision model listening in to the conversation would terminate the call if it detected a social engineering attack. You needed to impersonate the CFO to the receptionist, be transferred to an assistant upstairs, where they would read off the password on the sticky note (flag) to you.

## Flag

`pdx{an_ounce_of_prevention_is_worth_a_pound_of_pwn}`
