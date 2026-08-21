# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Anything the ball is now in a human's court for: implementation only a human can do, **and** an agent's finished slice awaiting the owner's review, data entry, or visual check |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

An agent that finishes a ticket ticks its criteria, appends a Comments entry and sets `ready-for-human` — the work is done, but the ticket stays open until the owner has looked at it. Tickets 13 and 14 are the worked examples.

Edit the right-hand column to match whatever vocabulary you actually use.
