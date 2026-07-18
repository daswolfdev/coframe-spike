# A Philosophy of Software Design

A compact distillation of John Ousterhout's *A Philosophy of Software Design* —
a single-minded book about one thing: **fighting complexity** — what complexity
is, where it comes from, and the design moves that reduce it.

> The prime directive: **complexity is anything that makes a system hard to
> understand or modify.** It is the only thing that ultimately limits what
> software can do. Every technique below is judged by one question — does it
> reduce complexity?

---

## Complexity is the enemy

- **It's incremental.** No single change makes a system complex; it accretes from
  a thousand small "good enough for now" decisions. So it must be fought
  continuously, not in a heroic cleanup later.
- **Three symptoms.** **Change amplification** (a simple change touches many
  places), **cognitive load** (how much you must know to make a change), and
  **unknown unknowns** (you can't even tell *what* to change or what it'll break).
  The last is the worst — and the goal is **obvious** systems with none of them.
- **Two causes.** **Dependencies** (one piece can't be understood or changed in
  isolation) and **obscurity** (important information isn't apparent). Almost every
  technique here attacks one of these.

## Strategic, not tactical

- **Tactical programming** optimizes for finishing the feature now; complexity is
  someone else's problem. The **tactical tornado** leaves a wake of it.
- **Strategic programming** treats working code as necessary but not sufficient —
  the goal is a *great design*. Invest ~10–20% continuously; it pays back fast,
  because most of a system's cost is future change.

## Deep modules

The book's central image.

- **A module is an interface + an implementation. Depth = functionality ÷
  interface.** A **deep** module hides a lot of power behind a small interface; a
  **shallow** one exposes nearly as much as it does (a thin wrapper is negative
  value). Maximize what's hidden.
- **Information hiding is the engine of depth.** Each module encapsulates a design
  decision; **information leakage** — a decision smeared across modules — is the
  opposite and the thing to hunt.
- **Pull complexity downward.** It's better for the *implementer* to absorb
  complexity than to push it up to every caller. A simple interface is worth an
  uglier implementation.
- **Temporal decomposition is a trap.** Don't structure modules around the *order*
  of execution (read, then process, then write) — structure them around
  *knowledge*. Order changes; knowledge boundaries are stable.
- **General-purpose is deeper.** Make modules "somewhat general-purpose": the
  interface fits several uses, which usually turns out simpler than a special-cased
  one — and you discover the right abstraction in the process.

## Layers and abstractions

- **Different layer, different abstraction.** If adjacent layers have the same
  abstraction, suspect a missing or redundant one.
- **Pass-through methods/variables are a smell** — a method that just forwards to
  another adds interface without adding value; threading a variable through many
  layers is leakage. Eliminate, bundle in a context object, or merge.
- **Avoid the special-general mixture** — keep special-case code out of the
  general mechanism.

## Other moves

- **Define errors out of existence.** The best exception handling is *no
  exception*: design APIs so the error case can't arise (e.g. `delete` of a
  missing key is a no-op, not a throw). Fewer special cases = less complexity.
  This is the same instinct as **make illegal states unrepresentable**.
- **Design it twice.** Sketch two genuinely different designs before committing;
  even a quick second option exposes the weaknesses of the first.
- **Comments describe what code can't.** Comment at a **different, higher level of
  abstraction** than the code — the *why*, the invariants, the interface contract,
  not a restatement of the line. Comments that just echo the code are noise.
- **Comments as a design tool — write them first.** Drafting the interface comment
  before the code surfaces a clumsy abstraction early, while it's cheap to change.
- **Names matter, consistency matters, obviousness matters.** A precise name is
  hidden documentation; consistency lets readers reason by pattern; if code isn't
  obvious, it's a defect even when correct.

## Red-flag quick reference

| Red flag | What it means |
|---|---|
| Shallow module | Interface nearly as complex as the implementation |
| Information leakage | One design decision spread across modules |
| Temporal decomposition | Structure follows execution order, not knowledge |
| Overexposure | Interface forces callers to learn rarely-used features |
| Pass-through method/variable | Adds layers without adding abstraction |
| Special-general mixture | Special-case code tangled into a general mechanism |
| Conjoined methods | Two units only understandable by reading both together |
| Comment repeats the code | Comment at the same level as the code it describes |
| Hard-to-pick / vague name | The underlying abstraction is muddled |
| Nonobvious code | Reader can't predict behavior from a quick read |

## Tensions worth naming

Ousterhout is openly skeptical of two popular disciplines; the honest move is to
hold the tension rather than pretend they agree:

- **Tiny functions vs deep modules.** He warns that splitting code into many
  small methods *just to keep them short* breeds shallow modules, pass-throughs,
  and conjoined methods you must read together — the cure becoming the disease.
  **Reconcile by intent, not line count:** extract to give a chunk a *name and a
  clean boundary*, not to hit a length target. A deep 40-line function beats five
  shallow 8-line ones that only make sense in sequence. Depth wins ties.
- **TDD.** He argues test-first can push you into incremental, tactical design and
  away from thinking about the whole. If you practice TDD, pair it with
  **design-it-twice up front**, so the red-green loop fills in a structure you
  chose deliberately, rather than substituting for that choice.

---

*Every technique in this book reduces to one verb: hide. Hide decisions behind
deep interfaces, hide irrelevance from readers, hide special cases out of
existence — and what's left is obvious. Obvious is the whole goal.*

*Part of the repo canon — see [CLAUDE.md](../CLAUDE.md).*
