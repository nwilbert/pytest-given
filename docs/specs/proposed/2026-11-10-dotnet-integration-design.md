# .NET Integration — Design Spec

## Goal

Let C# test suites narrate scenarios the way pytest-given suites do: given/when/then blocks inline
in ordinary test bodies, step text with typed values and term refs, parametrized tests merged into
one scenario with a parameter table, a glossary and stories. The C# side only *captures*. Grouping,
glossary resolution, kind inference, the runtime half of the narration lint, citations and every
renderer stay in Python, reached through a new `pytest-given ingest` command.

## Intent

A pytest-given report reads the same whatever produced it, so the report is the product and the
pytest plugin is one way to feed it. .NET teams have code-first BDD tools (LightBDD, BDDfy) and a
Gherkin tool (Reqnroll), but none narrates plain test bodies inline, and none carries a glossary,
stories, parameter tables or citations. A thin C# capture layer opens all of that to them at the
cost of one cross-language contract, the capture file.

Keeping the C# side thin is the point. Grouping is the hardest code in this repository, and two
implementations of it would drift. So the capture file holds exactly what pytest-given's own
capture holds before `group_parametrized` runs, and everything downstream is shared.

## Goals, non-goals, anti-goals

**Goals**

- A C# authoring surface that feels native: attributes for scenario metadata, `using` blocks for
  steps, interpolated strings for step text, typed glossary handles with IntelliSense.
- First-class support for xUnit.net v3 (4.x), the most widely used .NET test framework, with an
  adapter seam small enough that TUnit and MSTest each cost one class.
- Parametrized tests (`[Theory]` with `[InlineData]`, `[MemberData]`, `TheoryData<…>`) merged into
  one scenario with a parameter table, under the same rules pytest-given applies.
- The static half of the narration lint (the rules that read a step body's syntax) as Roslyn
  analyzers, so findings show in the IDE as the author types.
- `pytest-given ingest` turns one or more capture files into the normal report JSON, HTML or
  Markdown, with the same flags as `pytest-given report`.

**Non-goals**

- F# and VB. Their string interpolation offers no handler hook, so typed step text is out of reach.
- NUnit at first. It reaches Microsoft.Testing.Platform only through the VSTest bridge, and its
  `TestContext` model differs the most. The adapter seam leaves the door open.
- VSTest. The integration requires Microsoft.Testing.Platform (MTP), which the .NET 10 SDK's
  `dotnet test` runs natively and which xUnit v3, TUnit and MSTest all host.
- Gherkin feature files.
- Java and Kotlin. [Out of scope: Java and Kotlin](#out-of-scope-java-and-kotlin) records what an
  integration would build on.

**Anti-goals**

- Re-implementing grouping, glossary resolution, kind inference or rendering in C#.
- A second report format. The capture file is an input to `ingest`, never something a viewer or a
  citation reads.
- Weaving or IL rewriting. Everything works through public compiler features and test-framework
  extension points.

## The .NET test landscape, and where to hook in

pytest gives pytest-given one host with hooks for everything: collection, per-test setup, the
call, the outcome and session finish. .NET splits that across two layers.

- **The test framework** owns discovery, the per-test lifecycle and the *current test*:
  xUnit.net's `TestContext.Current`, TUnit's `TestContext.Current`, MSTest's `TestContext`.
- **Microsoft.Testing.Platform** owns the process: command-line options, the session lifetime and a
  message bus that carries every test result (`TestNodeUpdateMessage`) to in-process extensions.
  xUnit v3 hosts MTP natively (v2 of the platform since xUnit 4.0, August 2026), TUnit is built only
  on MTP, and MSTest 4 runs on it too.

**xUnit.net v3 is the first target.** It is the most widely used framework and the usual pick for
new projects, and its v3 line added the two things this design needs: `TestContext.Current` to
reach the running test from anywhere, and native MTP hosting. **TUnit is the second target**: it
is the modern, source-generated challenger with a `TestContext.Current` of its own, so it costs one
adapter class. MSTest follows the same pattern later.

**The design hooks into both layers, each for what only it can answer.** The framework adapter
answers "which test is running, with which arguments?". The MTP extension answers "how did each
test end, and when does the session finish?". No framework-specific results API is used, so most
of the integration is shared across frameworks.

## Architecture

```
 C# test project                                        Python (unchanged downstream)
┌──────────────────────────────────────────────┐
│ GivenNet.Core        steps, StepText handler,│
│                      recorder, capture writer│
│ GivenNet.Xunit       ICurrentTest over       │       pytest-given ingest *.capture.json
│                      TestContext.Current     │──────▶  read + validate capture
│ GivenNet.Platform    MTP extension: options, │ JSON     group_parametrized
│                      results, session end    │          resolve glossary, infer kinds
│ GivenNet.Analyzers   lint rules, glossary    │          runtime lint rules
│                      source generator        │          emit_sinks → JSON / HTML / MD
└──────────────────────────────────────────────┘
```

Package names are working names. `Given` alone is too generic for a NuGet id and collides with the
static `Given(...)` method, so the namespace is `GivenNet` (see [Open questions](#open-questions)).

`GivenNet.Core` depends on no test framework. `GivenNet.Xunit` and `GivenNet.TUnit` each reference
Core and their framework. `GivenNet.Platform` references Core and
`Microsoft.Testing.Platform` and registers itself through a `TestingPlatformBuilderHook` in the
package's `.props`, so a project gets it by referencing the adapter, which depends on it.
`GivenNet.Analyzers` ships inside the Core package as an analyzer asset.

## Authoring

### A first example

The coffee shop example, in C#:

```csharp
using GivenNet;
using GivenNet.Xunit;
using static GivenNet.Steps;

namespace Shop.Tests;

public sealed class CoffeeTests
{
    private readonly CoffeeMachine machine;

    public CoffeeTests()
    {
        using (Given("a coffee machine with 10 coffees"))
        {
            machine = new CoffeeMachine(coffees: 10, price: 2);
        }
    }

    [Fact, Scenario("Buying a coffee takes one from the machine", Tags = ["checkout"])]
    public void Buying_a_coffee()
    {
        using (When("I buy a coffee"))
        {
            machine.Buy();
        }
        using (Then("the machine has 9 coffees left"))
        {
            Assert.Equal(9, machine.Coffees);
            Attach("Machine state", machine.State);
        }
    }

    [Theory, Scenario("Paying for a coffee", Tags = ["pricing"])]
    [InlineData(1, false, Label = "a-euro-short")]
    [InlineData(2, true)]
    [InlineData(3, true)]
    public void Paying(int euros, bool served)
    {
        bool paid;
        using (When($"I pay {euros} €"))
        {
            paid = machine.Pay(euros);
        }
        using (Then($"the coffee {served:is served|is refused}"))
        {
            Assert.Equal(served, paid);
        }
    }
}
```

`Paying` reports as one scenario with a parameter table of three rows, `euros` and `served` as
columns, and `a-euro-short` as a custom case id. The constructor's `given` leads every scenario in
the class, because xUnit builds a new instance for each test.

### Python to C#, at a glance

| pytest-given | C# |
|---|---|
| `@scenario('Title', tags=[…])` | `[Fact, Scenario("Title", Tags = […])]` |
| `@scenario(..., group_parametrized=False)` | `[Scenario("…", GroupCases = false)]` |
| `@scenario(Template('… {col} …'))` | `[Scenario("… {col} …")]`: an attribute string is always template-shaped |
| `with given(t'… {x} …'):` | `using (Given($"… {x} …")) { … }` |
| `when_then(w, t)` + `pytest.raises` | `WhenThen(w, t, () => Assert.Throws<E>(…))` |
| `attach(label, content)` | `Attach(label, content)` |
| `@pytest.fixture` + `@given('label')` | `[GivenFixture("label")]` on a fixture class, or a `Given` block in the constructor |
| `Annotated[str, given(Template('{x}'))]` | `[Given("… {x} …")] string x` on a theory parameter |
| `@when(Template('I insert {amount}'))` helper | a helper whose body is `using (When($"I insert {amount}")) …` |
| `g['Guest']`, `.l`, `.s`, `g['x']('other')` | `Pg.Guest`, `.L`, `.S`, `Pg.X.As("other")`, or `Pg["Guest"]` |
| `story(title, [sentence(…)])` | a class deriving from `Story` |
| `pins=[story['name']]` | `[Pin<CheckoutStory>("name")]`, `pins: [Pin.Of<CheckoutStory>("name")]` |
| `-m pytest_given` | `--filter-trait "given=scenario"` |

### Scenarios

`[Scenario(title)]` marks a test for the report. It sits next to the framework's own test
attribute (`[Fact]`, `[Theory]`, `[Test]`) rather than replacing it, so every framework feature
(`Skip`, `Timeout`, `Explicit`, data attributes) keeps working unchanged. Each adapter ships its own
`ScenarioAttribute`, deriving from Core's, because each framework marks tests its own way: the
xUnit one implements `ITraitAttribute` and adds the trait `given=scenario`, so
`--filter-trait "given=scenario"` selects the scenarios as `-m pytest_given` does.

Named arguments: `Tags` (`string[]`), `Stories` (`Type[]`, each deriving from `Story`),
`GroupCases` (`bool`, default `true`). Pins take their own attribute, `[Pin<TStory>("name")]` or
`[Pin<TStory>(3)]`, repeatable, because an attribute argument cannot hold a sentence handle.
`[NoPins]` states the scenario's own pins as empty, as `pins=[]` does.

The scenario's source location comes from `[CallerFilePath]` and `[CallerLineNumber]` on the
attribute's constructor, which the compiler fills at the attribute's position, the same trick xUnit
v3's `FactAttribute` uses for its own source information.

**Attribute strings are template-shaped.** An attribute argument must be a compile-time constant,
so a title cannot hold a typed handle. Titles, `[GivenFixture]` labels and `[Given]` parameter
labels therefore read the `Template` grammar from a constant string:

- `{name}`, `{name:format}` is a placeholder naming a theory parameter, filled per case. Bare
  identifiers only, as with `Template`.
- `{name:true phrase|false phrase}` words a Boolean, as in Python.
- `{@Term}`, `{@Term.l}`, `{@Term.s}`, `{@Term.l.s}` and `{@Term:other form}` are term refs, resolved
  against the glossary.
- `{{` and `}}` are literal braces.

The analyzer checks every placeholder against the method's parameters and every term token against
the glossary at compile time (rules `GIVEN010` and `GIVEN011` below). A title that combines a term
ref with a per-case value is allowed in C#, unlike Python: Python's restriction comes from
evaluating t-string titles at import time, and a constant template has no such moment.

### Steps

`Given`, `When` and `Then` are static methods on `GivenNet.Steps`, imported with
`using static GivenNet.Steps;`. Each comes in two shapes.

**The block shape** returns an `IDisposable` step scope:

```csharp
using (When($"the guest cancels booking {booking.Id}"))
{
    response = await api.CancelAsync(booking.Id);
}
```

It is the primary shape because it keeps the body ordinary code. Locals assigned inside stay
definitely assigned after it, `await` works inside it, and an exception passes straight through.
The step opens when `When(...)` returns and closes when the block exits, either way.

**The expression shape** takes the body as a delegate and returns its result:

```csharp
var receipt = Given("a printed receipt", () => Receipt.For(order));
var total = await When("the total line is read back", () => reader.ReadTotalAsync(receipt));
Then("it shows the 2.00 total", () => Assert.Equal(2.00m, total));
```

Overloads cover `Action`, `Func<T>`, `Func<Task>` and `Func<Task<T>>`. It suits one-liners and
values a later step needs. A delegate cannot assign a local the caller reads afterwards without
tripping the compiler's definite-assignment check, so multi-statement bodies use the block shape.

**The using declaration is rejected.** `using var _ = When(...);` would hold the step open to the
end of the method, nesting every later step inside it. The analyzer reports it as an error
(`GIVEN001`), and the runtime catches what slips through: the next `Then` would nest inside a
`When` and raise.

**Nesting follows Python's rules.** A step may nest inside a step of the same phase, and a step of
another phase raises `GivenException`, which fails the test. A scope disposed out of order (an
outer step closing while an inner one is open) raises too. Disposing a scope twice does nothing.

**`WhenThen(whenText, thenText, body)`** records a `when` around the body and a sibling `then` once
the body returns normally, the C# shape of `when_then`. The delegate form makes "the body exited
cleanly" trivial to detect, which a `using` block's `Dispose` cannot do.

**`Attach(label, content)`** attaches to the innermost open step. A `string` is stored as text,
anything else serialized with `System.Text.Json` as `json`. Called with no step open, it raises.

### Step text: the `StepText` handler

Every step method takes its text as `StepText`, a type marked `[InterpolatedStringHandler]`. That
compiler feature, available since C# 10, is the exact counterpart of Python's t-strings: for
`$"I pay {euros:0.00} €"` the compiler calls `AppendLiteral("I pay ")`, then
`AppendFormatted(euros, "0.00")`, then `AppendLiteral(" €")`, instead of building a string. Each
call becomes one narration part.

- **`AppendLiteral(string)`** records a `NarrationLiteral`.
- **`AppendFormatted<T>(T value, string? format = null, [CallerArgumentExpression(nameof(value))] string expression = "")`**
  records a `NarrationValue` with the rendered value, the hole's source text as `expression`, and
  the format string as `format_spec`. `CallerArgumentExpression` on an `AppendFormatted` parameter is
  established practice (structured-logging handlers name their placeholders this way). It gives the
  expression text pytest-given matches against parametrize columns.
- **`AppendFormatted(TermHandle)`** records a `NarrationTermRef`.
- **A Boolean phrase spec** (`{served:is served|is refused}`) is handled by the handler itself,
  since `bool` has no format strings. A non-`bool` value with a phrase spec raises, as in Python.
- **Alignment** (`{x,10}`) is rejected by the analyzer (`GIVEN012`) and raises at run time: it pads
  for a monospaced console and has no meaning in a narrated sentence.
- **Values render with the invariant culture**, so a report reads the same on every machine.
  `IFormattable` values get their format string, anything else `ToString()`, `null` renders as
  `null`. `[assembly: GivenCulture("de-DE")]` overrides it for a suite narrated in another
  language.
- **A plain `string` converts implicitly** to a `StepText` of no parts, exactly Python's plain
  string. Concatenation and `string.Format` produce a plain string too, so text that varies between
  cases fails the run under grouping's existing rule, and the analyzer flags it earlier
  (`GIVEN013`).

### Theories and parameter tables

A `[Theory]` with `[Scenario]` is grouped like a parametrized pytest test. The parameter names come
from the test method's parameters, the values from the case's arguments, which the adapter reads
from the framework's current-test context.

A hole whose expression equals a theory parameter's name narrates that column, subject to the same
rebound-parameter rule pytest-given already applies: the cell has to read the way the hole
rendered. Python decides that by re-rendering the raw value with Python's `format()`, which cannot
read .NET format strings such as `C2` or `yyyy-MM-dd`. So the C# side renders instead: whenever a
hole names a parameter, the handler also renders that parameter's *original* argument with the
hole's format string and records the pair in the case's `renderings`. Grouping looks a rendering
up there rather than calling `render_interpolation` (see [Python-side changes](#python-side-changes)).

The original argument is the instance the framework passed in. `[InlineData]` arguments are
compile-time constants and cannot be mutated. A `[MemberData]` object mutated in place before the
hole renders is the same best-effort limit Python's `snapshot_param_value` documents.

**Case ids** follow pytest's shape so `node_base`, `case_suffix` and the parameter table work
unchanged: each argument rendered with the invariant culture, joined with `-`. A data row's `Label`
(xUnit 4, exposed as `TestContext.Current.Test.TestLabel`) or TUnit's `DisplayName` is a custom id
and sets `custom_id`. Duplicate ids get pytest's numeric suffixes.

**`[Given("a {size} cup")] string size`** on a theory parameter is the counterpart of
`Annotated[str, given(Template(…))]`. Its placeholders must name that parameter (`GIVEN010`).

### Setup as `given` steps

pytest-given turns fixtures into `given` steps. .NET splits setup three ways, and each gets one
mechanism.

- **Per-test setup** (the test class's constructor, xUnit's `IAsyncLifetime.InitializeAsync`,
  TUnit's `[Before(Test)]`) runs inside the test's context, so ordinary `Given` blocks record
  directly. Only `given` steps are allowed there (`GIVEN002`, and a runtime check).
- **Shared fixtures** (`IClassFixture<T>`, collection fixtures, assembly fixtures) are built once,
  outside any test, so they cannot record per test. Their class takes `[GivenFixture("label")]`
  with a constant label instead, and every scenario whose class consumes the fixture gets that
  `given` step, as a cached pytest fixture does. A `Given(...)` call inside a shared fixture records
  nothing and warns once.
- **Theory parameters** take `[Given(...)]`, as above.

The order in a scenario is shared fixtures (outermost scope first, then declaration order),
parameter labels in parameter order, constructor and `InitializeAsync` steps, then the body. That
matches pytest's fixture-setup order as closely as .NET's lifecycle allows.

Steps after the test body (in `Dispose` or `[After(Test)]`) raise, as a step after a fixture's
`yield` does.

### Helpers

A helper narrates itself by opening its own step:

```csharp
private void InsertCoins(int amount)
{
    using (When($"I insert {amount} coins"))
    {
        machine.Insert(amount);
    }
}
```

That replaces both Python helper decorators and their `Template`: the handler records `amount`
as the expression, which is what a `Template` placeholder on a decorated helper records. An
`async Task` helper works the same way. Calling a helper of another phase inside an open step
raises, as in Python.

### Glossary

**A file glossary is the default, and the C# side generates typed handles from it.** The project
lists the Markdown file as an additional file:

```xml
<ItemGroup>
  <AdditionalFiles Include="../../GLOSSARY.md" GivenGlossary="Pg"
                   GivenTermColumn="Term" GivenKindColumn="Kind" />
</ItemGroup>
```

A source generator in `GivenNet.Analyzers` reads the table and emits `internal static partial class
Pg` with one `TermHandle` property per term, carrying the definition as its XML doc comment. So
`Pg.Guest` autocompletes, shows its definition on hover, and a misspelled term is a compile error.
Property names are the term in PascalCase (`File glossary` becomes `Pg.FileGlossary`). Two terms
that collide report `GIVEN020` and stay reachable through `Pg["File glossary"]`, which the analyzer
also checks against the table. A handle offers `.L`, `.S` and `.As("other form")`, the C# spelling
of `.l`, `.s` and the called form.

The generator also records the glossary file's path and column options in an assembly attribute,
and the capture file carries them, so `ingest` loads the same file with Python's `FileGlossary`.
That file is the authority: the generator's parse only offers handles and early errors. When the
two parsers disagree on a name, `ingest` fails with the unresolved term refs listed, so a parser
difference can never mislabel a term.

**A code glossary** builds terms where the tests live:

```csharp
public static class Language
{
    public static readonly Glossary Pg = new();
    public static readonly TermHandle Guest = Pg.Actor("Guest", "Person booking accommodation.");
    public static readonly TermHandle Book = Pg.Activity("book", "Reserve a room for a stay.");
}
```

`[assembly: GivenGlossary(typeof(Language))]` registers it, the counterpart of binding a glossary
in `conftest.py`. The capture file carries its terms with each one's source location, and `ingest`
builds the `model.Glossary` from them. One glossary per suite, as in Python.

### Stories

A story is a class, so an attribute can name it with `typeof`:

```csharp
public sealed class CheckoutStory() : Story("Checking out",
    Sentence(Pg.Guest, Pg.Places, "an", Pg.Order, name: "place"),
    Sentence(Clause(Pg.Barista, Pg.Brews, Pg.Coffee), Clause(Pg.Barista, Pg.Serves, Pg.Guest)));

[Fact, Scenario("A guest orders a flat white", Stories = [typeof(CheckoutStory)])]
public void Ordering() { … }
```

Step pins take `Pin.Of<CheckoutStory>("place")` or `Pin.Of<CheckoutStory>(1)`:
`When("…", pins: [Pin.Of<CheckoutStory>("place")])`. An unknown sentence name raises at the call,
and the analyzer reports a constant one it can read (`GIVEN021`). Stories are found through the
`Stories` and `Pin` attributes of the assembly's scenarios and through
`[assembly: GivenStories(typeof(…), …)]` for stories no scenario names yet. The capture file
carries each story with its sentences' parts as term names, and Python's kind inference runs over
them unchanged.

## Runtime capture

### Finding the current test

Every step call asks the adapter for the current test through one interface:

```csharp
public interface ICurrentTest
{
    // null outside a test: in a shared fixture, a static constructor, a background thread
    // that outlived its test.
    TestIdentity? Current { get; }
}

public sealed record TestIdentity(
    string Key,                 // the id the MTP result for this test carries
    MethodInfo Method,
    IReadOnlyList<object?> Arguments,
    string? Label);
```

The xUnit adapter implements it over `TestContext.Current.Test`. The TUnit adapter implements it
over `TestContext.Current`. Adapters register through an assembly attribute in their package, so a
test project never wires anything up.

### Recorders

The Core keeps one recorder per running test, in a `ConcurrentDictionary` keyed by
`TestIdentity.Key`, created lazily by the first step call. A lazy recorder needs no
before-test hook, which is why constructor steps record without any framework cooperation, and why
the adapter surface stays one property.

The open steps live in an `AsyncLocal<StepNode?>`, where each node points at its parent and never
changes. `Given(...)` sets the slot to a new child node, and disposing its scope sets it back to the
parent. Because .NET restores an `AsyncLocal` at every async method boundary and nodes are never
mutated, concurrent branches inside one step (`await Task.WhenAll(A(), B())`, each opening its own
step) each see the right parent. Their steps append to the shared parent node in the order they
open, under a lock.

A step call from a test without `[Scenario]` records nothing and warns once per test, as
pytest-given's stray step does, through the platform's warning output.

### Outcomes, from the platform

`GivenNet.Platform` is one class implementing MTP's `IDataConsumer` and
`ITestSessionLifetimeHandler`, registered through `CompositeExtensionFactory` so both roles share
state. From each `TestNodeUpdateMessage` it takes:

- the status: passed, failed (`FailedTestNodeStateProperty`, `ErrorTestNodeStateProperty`,
  `TimeoutTestNodeStateProperty`), or skipped (`SkippedTestNodeStateProperty`, whose explanation
  becomes `skip_reason`). Nothing in xUnit or TUnit maps to `xfailed`, so they never report it.
- the duration, from `TimingProperty`.
- the exception, from the failed state's `Exception`.
- the method, from `TestMethodIdentifierProperty`.

At session finish it walks every result. A result whose method carries `[Scenario]` becomes a
case, with the recorder for its key if one exists and an empty step list otherwise, so a scenario
that narrates nothing still appears, as in Python. Then it writes the capture file.

Two facts need a spike before this is final (see [Spikes](#spikes)): that the key `ICurrentTest`
returns equals the `TestNode.Uid` the platform reports for the same test, and that xUnit puts a
real `Exception` on its failed state rather than a synthesized one. The fallback for the first is
matching on the method identifier plus the display name. The fallback for the second is a
`FirstChanceException` handler that remembers, per recorder, the last exception thrown inside the
test, used when its type and message match the reported failure.

### Tracebacks

The C# side builds `ErrorInfo` from the `Exception` object, never from stack-trace text: .NET
localizes the "at … in …:line N" wording, so parsing it would break on a German runtime.

- **Frames** come from `new StackTrace(exception, fNeedFileInfo: true)`, one `TracebackFrame` per
  frame with file information. `code` is the frame's source line, read from the file, which is on
  disk while tests run. Paths go through the same relativization as source locations.
- **`is_internal`** is true for frames in the `GivenNet`, `Xunit`, `TUnit`, `System` and
  `Microsoft` namespaces, and for methods marked `[StackTraceHidden]`.
- **`error_tail`** is `ExceptionType: message`.
- **Causes** come from `InnerException`, root first, as pytest prints chained exceptions. The
  connector reads "The exception above caused the one below." `TargetInvocationException` and a
  single-child `AggregateException` are unwrapped first, since they only record how the exception
  traveled.

### Source locations and node ids

Every source location is a path relative to the source root, POSIX-separated, plus a line, exactly
what `SourceLocation` holds. The C# compiler bakes absolute paths into `[CallerFilePath]` values,
and a deterministic CI build maps them through `PathMap` to `/_/…`. The capture writer handles both:

- A path under a `PathMap` target is relative already: the writer strips the target prefix.
- Any other path is made relative to `GivenSourceRoot`, an MSBuild property the package's
  `.props` defaults to the repository root (the directory holding `.git`) and bakes into an assembly
  attribute at build time.

A node id is `<relpath>::<Class>::<Method>[<case id>]`, for example
`tests/Shop.Tests/CoffeeTests.cs::CoffeeTests::Paying[2-True]`. A nested class reads
`Outer::Inner`. `module` is the test class's namespace-qualified name, the unit a C# reader thinks
of a file as.

## The capture file

The capture file is the cross-language contract, so unlike the report JSON it is versioned:
`capture_version` is an integer, and `ingest` refuses a version it does not know, naming the
`pytest-given` release that reads it. The C# package documents the lowest `pytest-given` version
that reads its output.

One file per test assembly, written at session finish to `--given-capture` (default
`TestResults/given/<assembly>.capture.json`). A sketch:

```json
{
  "capture_version": 1,
  "producer": {"name": "GivenNet", "version": "0.1.0",
               "framework": "xunit.v3 4.0.2", "runtime": ".NET 10.0.1"},
  "project": "Shop",
  "title": null,
  "report_url": null,
  "glossary": {"file": {"path": "GLOSSARY.md", "term_column": "Term",
                        "definition_column": 1, "kind_column": "Kind"}},
  "stories": [
    {"title": "Checking out", "source": {"relpath": "tests/Shop.Tests/Stories.cs", "line": 3},
     "sentences": [{"name": "place", "clauses": [{"parts": [{"term": "Guest"}, {"term": "places"},
                                                             {"word": "an"}, {"term": "Order"}]}]}]}
  ],
  "cases": [
    {
      "scenario": {"id": "tests/Shop.Tests/CoffeeTests.cs::CoffeeTests::Paying[2-True]",
                   "narration": {"text": "Paying for a coffee", "parts": []},
                   "module": "Shop.Tests.CoffeeTests", "tags": ["pricing"],
                   "status": "passed", "duration_ms": 3, "steps": ["…"],
                   "source": {"relpath": "tests/Shop.Tests/CoffeeTests.cs", "line": 31}},
      "params": {"names": ["euros", "served"], "values": [2, true],
                 "renderings": [{"name": "euros", "format_spec": "", "rendered": "2"}],
                 "group": true, "custom_id": false},
      "step_sources": [{"path": [0], "relpath": "tests/Shop.Tests/CoffeeTests.cs", "line": 36}]
    }
  ]
}
```

- **`scenario`** is the report schema's `Scenario`, ungrouped, as pytest-given's collector holds
  it before `group_parametrized`. The existing serde reads it, so the schema stays the single source
  of truth for its shape.
- **Term refs** carry the term's name in `term_id`. `ingest` derives the real id with the same
  function the Python glossary uses, so the slug rule lives once.
- **`params.values`** are JSON primitives, the cells of the parameter table. A non-primitive
  argument arrives as its invariant-culture `ToString()`, as Python coerces a non-primitive to its
  `str()`.
- **`step_sources`** are the step anchors the lint reads, which the report schema excludes from
  its JSON. Paths are the `StepPath` tuples.

## Python-side changes

### `pytest-given ingest`

```
pytest-given ingest CAPTURE.json [CAPTURE.json …] [-o OUTPUT] [--format json|html|md]
                    [--source-link …] [--theme …] [--lines …] [--report-url …] [--lint]
```

It reads every capture file, checks their versions, and merges them into one suite. A solution
with several test projects writes one capture per assembly and gets one report. Two captures that
name different glossaries fail, as two glossaries in one pytest suite do. Then it runs exactly
what the plugin's session finish runs: `group_parametrized`, glossary resolution, `infer_glossary_kinds`,
the undeclared-story warning, `ReportData`, and `emit_sinks`. With `--lint` it runs the runtime
lint rules and prints the same summary the plugin prints.

Flags and exit codes follow `pytest-given report`: 0 on success, 1 when grouping refuses, a
glossary or term ref does not resolve, or the lint finds an error, 2 on a usage error. `--lint` is
a flag here rather than a pytest option, but it reads the same `given_lint_*` settings from the
`[tool.pytest]` table of a `pyproject.toml` next to the first capture, when one exists.

### A rendering seam in grouping

`ParamSpec` gains `renderings: Mapping[tuple[str, str], str] | None`, keyed by parameter name and
format spec. The two call sites that re-render a raw value (`grouping/checks.py` and
`grouping/columns.py`) go through one function that looks the rendering up when `renderings` is
set and calls `render_interpolation` otherwise. The pytest path passes `None` and behaves exactly as
today. A missing rendering is an `ingest` error naming the case and the hole, since it means the
capture is incomplete, never that the narration is wrong.

### Metadata

`Metadata.pytest_version` becomes `runner`: `"pytest 9.2.0"` from the plugin,
`"xunit.v3 4.0.2 on .NET 10.0.1"` from a capture. `plugin_version` stays the pytest-given version
that built the report, and the producer's version joins it as `producer_version`, `None` for a
pytest run. This is a **Breaking** change to the report JSON, changelogged with its migration (a
`jq` reading `.metadata.pytest_version` reads `.metadata.runner`).

### Messages that name their fix

Grouping refusals and lint findings name their fix in Python terms: "use a t-string",
"`@scenario(..., group_parametrized=False)`". A C# author needs "use an interpolated string",
"`[Scenario(..., GroupCases = false)]`". The fixes move into a small `Dialect` table in `model/`,
one entry per authoring form, with a Python and a C# spelling. Each message takes its fix from the
dialect of the run: Python for the plugin, the capture's for `ingest`. The message's statement of
what is wrong stays shared. This is the largest Python-side change by line count, and the one that
keeps C# errors honest.

### What stays untouched

The renderers, the templates, `citations`, the report JSON's scenario shape and the HTML's deep
links. A report built by `ingest` is an ordinary report: `pytest-given report` re-renders it, and
`pytest-given citations` cites it.

## Static analysis

The pytest-given lint has two halves. The runtime rules read the recorded tree and run in `ingest`
unchanged. The rules that read a step body's syntax read Python's AST, so for C# they become
Roslyn analyzers in `GivenNet.Analyzers`, reported in the IDE and at build. They are configured the
.NET way, through `.editorconfig` severities and `#pragma warning disable`, which replaces
`given_lint_ignore` for these rules.

| Id | Severity | Rule |
|---|---|---|
| `GIVEN001` | error | A step scope held by a `using` declaration instead of a `using` block. |
| `GIVEN002` | error | A `when` or `then` step in a constructor, `InitializeAsync` or a before-test hook. |
| `GIVEN003` | error | A step of one phase nested lexically inside a step of another. |
| `GIVEN004` | warn | `[Scenario]` on a method with no test attribute of a known framework. |
| `GIVEN010` | error | A template placeholder that names no parameter of the method, or that holds anything but a bare identifier. |
| `GIVEN011` | error | A term token or `Pg["…"]` lookup naming no glossary term. |
| `GIVEN012` | error | An alignment component in a step's interpolated text. |
| `GIVEN013` | warn | Step text built by concatenation or `string.Format` in a `[Theory]`. |
| `GIVEN020` | warn | Two glossary terms that generate the same handle name. |
| `GIVEN021` | error | A constant pin naming no sentence of its story. |
| `GIVEN101` | error | `empty-step`: a step body with no statement that does anything, or, for `when` and `then`, only an `Attach` call. |
| `GIVEN102` | error | `then-without-check`: a `then` with no checking call. |
| `GIVEN103` | warn | `conditional-check`: a `then` whose checks all sit under an `if`, a loop, a `switch` or a `catch`. |
| `GIVEN104` | warn | `check-outside-then`: a checking call inside a `given` or `when`, the `WhenThen` body excepted. |
| `GIVEN105` | warn | `action-in-then`: no `when` performs an action, and a `then` folds it into its check. |
| `GIVEN106` | warn | `unused-interpolation`: a hole naming a local or parameter the step's body never uses. |

A *checking call* is a call on `Assert`, a call whose name starts with `Assert`, `Verify` or
`Should` (Shouldly, FluentAssertions, AwesomeAssertions), or `Assert.Throws`-style calls passed as a
`WhenThen` body. `given_check_methods` in `.editorconfig` extends the list. The `GIVEN1xx` rules
carry the Python rule's name in their title, so the lint documentation stays one catalog.

`missing-phase`, `tag-shadows-term` and `dead-term` read the recorded tree and run in `ingest`.

## Running it

```
dotnet test -- --given-capture
uvx pytest-given ingest TestResults/given/*.capture.json -o report.html
```

The MTP extension adds `--given-capture [PATH]` and `--given-report PATH`. The second writes the
capture and then runs `ingest` itself, through the command in `GIVEN_INGEST_COMMAND`, defaulting to
`uvx pytest-given==<lowest compatible version> ingest`. A missing `uvx` is a warning with the
manual command printed, never a failed test run. Settings that belong to the build
(`GivenSourceRoot`, `GivenTitle`, `GivenReportUrl`) are MSBuild properties, and options that
belong to a run go on the command line or into MTP's `testconfig.json`.

Outputs are opt-in, as with pytest-given: a bare `dotnet test` writes nothing.

## Repository layout and testing

The C# code lives in this repository under `dotnet/`, so a change to the capture contract and to
`ingest` lands in one commit. A `dotnet` nox session builds and tests it, and a CI job with the
.NET SDK runs that session.

- **Golden captures.** A C# example suite (the coffee shop and hotel booking examples, ported)
  writes its capture files into `examples/dotnet/`. `uv run nox -s dotnet_examples` regenerates them
  and their reports, and `reports_current` covers them like the Python examples. Python's
  `ingest` tests read the committed captures, so the Python suite tests the contract without a .NET
  SDK.
- **C# unit tests** cover the handler, the recorder and the analyzers (Roslyn's analyzer test
  harness), with no test framework involved.
- **End-to-end tests** run the example suite under xUnit and TUnit and compare the capture with the
  committed one.
- **Self-report.** The C# library's own tests are narrated with GivenNet, as the Python suite
  narrates itself.

The authoring skill gains a C# companion, `givennet-authoring`, shipped in the NuGet package and
installed by `pytest-given skills install --dotnet`. It restates the narration rules with the C#
spellings and shares the reviewing skill's rubrics.

## Phases

1. **Spikes**, in a throwaway xUnit v3 project (below).
2. **MVP.** Core, the xUnit adapter and the platform extension. Steps in both shapes, the handler
   with values and phrase specs, `Attach`, `[Scenario]` with tags, theories with case ids and
   renderings, the capture writer. On the Python side `ingest`, the rendering seam and `runner`.
   Term refs through `Pg["Guest"]` against a file glossary.
3. **Domain model.** The glossary generator, code glossaries, stories and pins, `[GivenFixture]`,
   `[Given]` parameters, and the `GIVEN0xx` analyzers.
4. **Lint and polish.** The `GIVEN1xx` analyzers, the `Dialect` messages, `--given-report`, the
   TUnit adapter, the C# skill.
5. **MSTest**, then NUnit, when someone asks.

## Spikes

Each spike answers one question with a running test project. The design changes only where a spike
says no.

1. **Correlation.** Does xUnit's `TestContext.Current.Test.UniqueID` equal the `TestNode.Uid` its
   MTP bridge reports, for facts, pre-enumerated theory rows and non-serializable `[MemberData]`
   rows? Same question for TUnit's test id. Fallback: the method identifier plus the display name.
2. **The exception object.** Does xUnit's failed state carry the original `Exception`? Fallback:
   the `FirstChanceException` record described above.
3. **The current test in setup.** Is `TestContext.Current.Test` set in an xUnit test class's
   constructor and `InitializeAsync`, and in TUnit's before-test hooks?
4. **The handler.** `CallerArgumentExpression` on `AppendFormatted` across net8.0 and net10.0. What
   the compiler passes when every hole of an interpolated string is a constant.
5. **Arguments.** Which xUnit 4 API exposes the current test's arguments, and does it hand over the
   instances the method received?
6. **Paths.** `[CallerFilePath]` under `PathMap`, `ContinuousIntegrationBuild` and Source Link, and
   finding the repository root when `.git` is a file (a worktree).
7. **Auto-registration.** A `TestingPlatformBuilderHook` in a NuGet `.props`, picked up by xUnit's
   and TUnit's generated entry points.

## Risks

- **Extensibility churn.** xUnit 4.0 broke many extensibility APIs. The design touches only
  `TestContext.Current` and the platform's message bus, both public and stable, and keeps each
  adapter to one class.
- **Two glossary parsers.** The generator and Python's `FileGlossary` both read `GLOSSARY.md`.
  `ingest` resolving every term ref against Python's parse keeps a disagreement from going unseen.
- **Version skew.** A NuGet release and a PyPI release must agree on `capture_version`.
  `--given-report` pins the `pytest-given` version it runs, and `ingest` refuses an unknown version.
- **Native AOT.** TUnit can run AOT-compiled, where reading attributes by reflection at session
  finish may be trimmed away. The generator can emit the scenario metadata as a table instead. Not
  in the MVP.

## Open questions

- **The name.** NuGet ids and the namespace need a name that is free on NuGet and says "the .NET
  side of pytest-given". `GivenNet` is a placeholder.
- **One repository or two.** This spec puts the C# code here for the contract's sake. A separate
  repository would suit a .NET contributor better, at the cost of the contract living across two.
- **TUnit before MSTest.** TUnit is the more modern target and the cheaper adapter. MSTest has the
  larger enterprise base. The order in [Phases](#phases) assumes the first matters more.

## Out of scope: Java and Kotlin

The capture file and `ingest` hold nothing specific to C#, so a JVM integration would reuse both
unchanged and add a spelling per language to the `Dialect` table. It is not part of this design.
This section records what it would build on.

**The JVM layer, shared by Java and Kotlin.**

- JUnit Jupiter (5 and 6) is the first target. `@Scenario` is meta-annotated with `@ExtendWith`,
  so the annotation alone registers the extension. `InvocationInterceptor` hands over a
  parameterized case's arguments.
- A JUnit Platform `TestExecutionListener`, registered through `ServiceLoader`, takes the MTP
  extension's part: outcomes and session finish. It sees every engine on the platform, Kotest and
  Spock included, under Maven Surefire and Gradle alike.
- `ExtensionContext.getUniqueId()` is the id the listener reports, and the listener's
  `TestExecutionResult` carries the real `Throwable`. Spikes 1 and 2 have no JVM counterpart.
- `ParameterResolver` is the counterpart of a shared fixture with `[GivenFixture]`. Per-test setup
  records from `@BeforeEach` methods and the constructor, since Jupiter builds an instance per test
  by default.
- `StackTraceElement` is structured, so tracebacks need no text parsing.
- Gradle and Maven plugins take the place of the MSBuild properties.

**Java.**

- A scenario reads `@Scenario(value = "…", tags = {"checkout"})`. Annotation arguments are
  constants and annotations cannot be generic, so a pin reads
  `@Pin(story = CheckoutStory.class, sentence = "place")`.
- Steps are try-with-resources blocks: `try (var _ = when("I buy a coffee")) { … }`, with the
  unnamed `_` from Java 22. Java has no `using` declaration, so `GIVEN001` has nothing to catch.
- Java has no string interpolation. String Templates were previewed in JDK 21 and 22 and withdrawn
  in JDK 23. Step text therefore takes the template grammar of attribute strings, filled by the
  arguments in order: `when("I pay {euros} €", euros)`. This is Python's `Template` authoring form.
- Nothing fills a source path or an expression text at the call. An annotation processor using
  javac's Compiler Tree API can index scenario source locations and parameter names, check each
  placeholder against its argument expression, and run the static lint rules. Its findings show at
  build, not as the author types.

**Kotlin.**

- An `inline` step function with a trailing lambda and a `callsInPlace(block, EXACTLY_ONCE)`
  contract replaces both step shapes: `val receipt = given("a printed receipt") { Receipt.of(order) }`.
  A `val` declared before the step may be assigned inside it, and a `suspend` test may suspend
  inside it. `when` is a keyword, so that step needs another name.
- String templates compile to concatenation. A compiler plugin can rewrite a template passed to a
  step function into the parts `StepText` records, with each hole's source text and the call's file
  and line, as Kotlin's power-assert plugin does for `assert`. Step functions take a plain `String`
  publicly, so code compiles without the plugin.
- Templates have no format-spec slot. Format strings and Boolean phrases become calls the plugin
  recognizes inside a hole: `"the coffee ${served.phrase("is served", "is refused")}"`.
- The compiler plugin API is unstable, so the plugin needs a release per Kotlin version. Without
  the plugin, Kotlin uses Java's template form.
- `operator fun get` and `operator fun invoke` give glossary handles Python's spellings:
  `Pg["Guest"]` and `Pg.X("other")`. KSP or a Gradle task generates the handles.
- A coroutine can resume on another thread, so the open steps travel in a `ThreadContextElement`
  rather than a bare `ThreadLocal`.
