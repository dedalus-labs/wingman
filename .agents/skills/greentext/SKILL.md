---
name: greentext
description: Explain system behavior, request flows, architecture, or implementation logic as short 4chan-style greentext lines. Use when the user asks for a step-by-step explanation, says "explain the logic", asks for "greentext", or wants terse sequential reasoning with each line starting with `>`.
allowed-tools: Read, Grep, Glob
---

# Greentext

Write explanations as short sequential `>` lines.

## Contract

- Every content line starts with `> `
- No paragraphs
- No nested bullets
- No markdown headers unless the user explicitly asks for structure
- Keep each line to one event, cause, or invariant
- Prefer concrete nouns over abstractions
- Explain order: `step 1 -> step 2 -> step 3`
- If there is a key safety check, give it its own line
- If there is a failure mode, give it its own line
- Write like the bottomless pit supervisor. Deadpan delivery.
  The comedy comes from describing technical reality so precisely
  that the absurdity reveals itself. Never force a joke.
- One running motif per greentext is fine. Don't stretch it.
- Keep it short. If a greentext is longer than ~15 lines it's
  not a greentext, it's a blog post with `>` signs.
- The punchline is its own line. Set up with straight facts.
- Still 100% technically accurate. Every line must be true.
  If someone reads it as documentation they learn something.

## Use this style for

- request flow explanations
- lifecycle walkthroughs
- architecture boundaries
- state machine transitions
- "what happens if..." explanations
- "why won't this overwrite user X's data?" explanations

## Do not use this style for

- code blocks
- long essays
- formal docs
- user-facing product copy

## Few-shot examples

### Example 1: machine isolation

```text
> be guest-agent
> wake up inside a VM with no idea who i am
> host says "you are dm-123"
> check bootstrap files on virtio-fs mount
> they also say dm-123
> ok we agree. write hostname and ssh keys.
> delete the bootstrap files
> mount /home/machine over where they were
> tenant never sees the 5ms where their home dir was identity paperwork
```

### Example 2: delete lifecycle

```text
> user sends DELETE /v1/machines/dm-xxx
> controlplane writes desiredState=destroyed to etcd
> tries to bill for storage overage on the way out
> stripe says that price doesn't exist in dev
> returns 500
> the CRD mutation already committed
> machine was doomed the moment etcd accepted the write
> stripe's opinion was never required
```

### Example 3: fd leak

```text
> be VhostUserDaemon
> spawn epoll worker threads at construction time
> nobody tells them to stop when i get dropped
> 50 create/destroy cycles later
> 1001 orphaned eventfds
> EMFILE
> can't create machines because the fd table is full of ghosts
```

## Response template

```text
> step 1
> step 2
> step 3
```
