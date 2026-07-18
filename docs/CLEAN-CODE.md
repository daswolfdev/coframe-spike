# Clean Code

A compact distillation of the durable principles (Martin's *Clean Code*, Fowler's
*Refactoring*, the *Pragmatic Programmer*). This is the *why* and the *taste*;
the theory of complexity lives in [SOFTWARE-DESIGN.md](./SOFTWARE-DESIGN.md).

> The prime directive: **code is read far more than it is written.** Optimize for
> the next reader — usually you, in six months.

---

## Names

- **Reveal intent.** `elapsedDays` not `d`. A name that needs a comment is a bad name.
- **Pronounceable, searchable, no encodings** — no Hungarian notation, no `m_` prefixes.
- **One word per concept** — don't mix `fetch`/`get`/`retrieve` for the same idea.
- **Length scales with scope.** Loop index `i` is fine; a module-level export is not.
- Avoid disinformation (`accountList` that isn't a List) and noise words (`Data`, `Info`, `Manager`).

## Functions

- **Small.** Then smaller. A function should do **one thing** at **one level of
  abstraction**. (But extract for a *name and a boundary*, not a line count —
  see the tension named in [SOFTWARE-DESIGN.md](./SOFTWARE-DESIGN.md).)
- **Few arguments** (0–2 ideal, 3 is a smell). Replace flag arguments and long
  parameter lists with an options object / struct.
- **No side effects the name doesn't promise.** `checkPassword` must not also init the session.
- **Command/query separation** — a function either *does* something or *answers*
  something, never both.
- **Return early.** Guard clauses over nested `if`; avoid deep nesting.
- Prefer **pure functions** for logic (no I/O, no clock, no globals) — trivially
  testable, the backbone of functional-core/imperative-shell.

## Comments

- **The best comment is the one you didn't need** because the code is clear.
- Comment **why**, not **what**. The code says what; only you know why.
- Delete commented-out code (that's what git is for) and don't narrate the obvious.
- Good uses: intent, consequences/warnings, safety invariants, links to a spec/issue.

## Formatting & structure

- **Be consistent**; let an autoformatter own it so it's never a debate.
- **Vertical proximity**: related things close together; a variable declared near first use.
- **Newspaper layout**: high-level first, details below; callers above callees.
- Keep files focused — one reason to exist. One public concept per file where practical.

## Error handling

- **Errors are values; use the type system.** `Result`/typed errors over exceptions
  for expected failures; reserve panics/throws for bugs.
- **Fail fast, fail loud** — validate at the boundary; never swallow an error silently.
- **Never return `null`/`undefined` as "no result"** when an `Option`/empty value
  models it; never pass `null` into a function that doesn't expect it.
- Provide context with the error, not a stack-trace autopsy.

## Design principles

- **DRY** — every piece of knowledge has one authoritative representation. But beware
  *false* DRY: two things that look alike but change for different reasons should stay apart.
- **YAGNI** — build what's needed now, not what might be. Delete speculative generality.
- **Rule of three** — don't abstract until the third occurrence; premature abstraction
  costs more than duplication.
- **Single Responsibility** — a module has one reason to change.
- **Open/Closed, Liskov, Interface-Segregation, Dependency-Inversion** — depend on
  abstractions (interfaces/traits), inject dependencies, keep interfaces small and role-specific.
- **Composition over inheritance.** **Make illegal states unrepresentable** — model
  with types so bad combinations don't compile.
- **Low coupling, high cohesion** — minimize what each part needs to know about others.
- **Principle of least astonishment** — code should behave the way its name and shape suggest.

## Tests as first-class code

- Tests are production code: **clean, named for behavior, one assertion-of-intent each.**
- **FIRST**: Fast, Independent, Repeatable, Self-validating, Timely.
- Test behavior, not implementation, so refactors don't break the suite.
- A failing test is a precise spec; write it first when you can (TDD).

## The Boy Scout Rule & refactoring

- **Leave the code cleaner than you found it** — small, opportunistic improvements
  compound. Scope it to the code your change already touches; unrelated cleanup is
  its own commit.
- **Refactor in small, behavior-preserving steps**, green tests between each.
- Treat smells as prompts: long function, large class, long parameter list, feature
  envy, shotgun surgery, primitive obsession, duplicated code.
- Pay down tech debt deliberately and name it; don't let "temporary" become permanent.

## Code-smell quick reference

| Smell | Fix |
|---|---|
| Long function / deep nesting | Extract function; guard clauses |
| Long parameter list / flag args | Introduce parameter object; split the function |
| Duplicated code | Extract once it earns it (rule of three) |
| Comment explaining *what* | Rename / extract until the comment is redundant |
| Primitive obsession | Newtype / value object (`UserId`, not `string`) |
| Feature envy | Move the method to the data it uses |
| Shotgun surgery | Consolidate the scattered responsibility |
| Boolean blindness | Replace with a descriptive enum/union |

---

*The rules are servants, not masters. Clarity is the goal; when a rule fights
clarity, clarity wins — and you say why in the review.*

*Part of the repo canon — see [CLAUDE.md](../CLAUDE.md).*
