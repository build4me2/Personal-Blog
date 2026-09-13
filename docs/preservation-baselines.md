# Content and presentation preservation baseline

Initialize the repository's pinned build inputs, then run the exact scoped
validation entrypoint from the repository root:

```sh
make setup
hugo version # must report v0.162.0 with Extended capabilities
make validate
```

`make validate` is the only acceptance-suite entrypoint. It delegates to
`scripts/run_validation.py`, which provides stable global test ordering and
normalizes runtime-only report values. Do not invoke the test framework's raw
discovery mode directly: that bypasses deterministic report generation. Repeated
successful and failing CLI runs are covered by command-level comparison tests.

`setup_pinned_theme.py` verifies and expands the committed PaperMod snapshot,
reconstructs its exact `154d006e0182dfc7da38008323976b02e6bfab4a` Git checkout,
and performs no clone, fetch, or other network operation. It is safe to rerun.
An existing checkout is accepted only when its HEAD, complete tracked index/worktree,
and all untracked files exactly match that commit. Modified, deleted, and untracked
paths (including ignored files) are rejected with path-sorted diagnostics rather
than silently preserving a local theme customization; restore or remove the named
paths and rerun setup.
This makes acceptance work in a fresh validation worktree even when submodule
network access is disabled. A normal recursive checkout remains supported for
contributors with network access; the offline setup command is the deterministic
validation path.

The scoped suite includes a real invocation of the full preservation validator,
so success proves that the checked-out PaperMod commit and local Hugo binary can
render non-empty home and article responses. The validator independently applies
the same complete PaperMod worktree check before rendering, so a theme CSS or
variable mutation cannot pass merely because the submodule HEAD remains pinned.
It does not replace build inputs with mocks for that acceptance test. The remaining mutation tests use temporary
fixtures and do not access the network. To run the same integration acceptance
directly, use:

```sh
python3 scripts/validate_preservation_baseline.py
```

The rendering toolchain is pinned to **Hugo Extended 0.162.0**. PaperMod's pinned README requires Hugo 0.146.0 or newer, so this exact release satisfies the theme requirement and is proven by the repository's real four-route build acceptance. Install that exact Extended release from the [Hugo releases](https://github.com/gohugoio/hugo/releases/tag/v0.162.0) before validating; do not substitute a newer patch or a standard build. `.hugo-version` is the machine-readable local-tooling pin (supported by common version managers), and GitHub Pages uses the same exact version through `HUGO_VERSION` in `.github/workflows/hugo.yml`. The validator cross-checks both declarations against the immutable build contract and rejects floating versions, a standard Hugo binary, duplicate declarations, or drift between local and Actions tooling.

PaperMod remains a Git submodule pinned by the repository gitlink to commit **`154d006e0182dfc7da38008323976b02e6bfab4a`**. A clean checkout may use `git clone --recurse-submodules` (or `git submodule update --init --recursive`); `python3 scripts/setup_pinned_theme.py` provides the documented network-free equivalent from the digest-pinned committed snapshot. Both paths are accepted only when the resulting theme HEAD and complete worktree match that exact commit.

`make validate` is the required acceptance command; it includes the full
`python3 scripts/validate_preservation_baseline.py` integration invocation. A
direct validator run is an integration diagnostic, and a `--source-only` run is
a narrower diagnostic; neither replaces the complete acceptance suite. Both
validator modes first inspect the local `hugo env` output without accessing the
network and report the expected and observed toolchains on a version or
Extended-capability mismatch. Initialize the pinned theme first. The validator checks both the committed PaperMod gitlink and the checked-out worktree commit before invoking Hugo; an absent or stale checkout reports the exact offline `python3 scripts/setup_pinned_theme.py` recovery command instead of an indirect template error. The full check builds with an isolated cache in a temporary directory and leaves no `public/` tree. The mutation tests are also offline: they use temporary fixtures to prove that toolchain mismatches, empty HTTP route responses, missing routes, titles, listing entries, header/footer/theme-toggle markers, prose segments, configuration, templates, and styles produce focused failures. Adversarial project overrides at PaperMod core CSS, common CSS, and JavaScript paths are covered explicitly.

## What is protected

`tests/baselines/preservation.json` is a reviewable inventory of:

- the four established source files, route slugs, titles, dates, and complete front matter;
- hashes of each exact essay body, each normalized prose segment, and its normalized rendered prose;
- every citation destination, including repeats and order, in both source and output;
- exact essay wording anchored to each article at `capturedFrom`, so changing both a post and its editable hash cannot hide an argument change;
- citation changes relative to `capturedFrom`, each of which must consume one exact, evidence-backed review record;
- the established articles' presence and relative order on the home page;
- canonical rendered element structure for the home and article pages;
- complete, sorted file inventories and hashes for local layouts and the entire project `assets/` tree, including header, footer, listing, citation, theme-toggle, core/common CSS, and JavaScript overrides (new asset or layout files are rejected);
- the exact Hugo Extended version, behavior-relevant Hugo settings (including the reviewed `defaultTheme = "dark"`), and the PaperMod gitlink commit.

The validator checks the baseline schema before reading any fixture values. Missing fields, incorrect JSON types, malformed hashes, and an incorrect established-entry count fail with sorted JSON-path diagnostics and no traceback. Merely retaining four array entries is insufficient: article source paths, titles, slugs, and routes must be unique, home routes must be unique, and the home routes must map one-to-one to the article routes. The canonical identity tuples are independently derived from every established post in the pinned `capturedFrom` Git tree, so duplicating one entry to hide an omission or substitution cannot rebaseline the identity set. It then fails with a focused diagnostic when any protected value changes. Rewriting the editable baseline alongside a change does not bypass preservation: article front matter and derived routes/listing are reconstructed from `capturedFrom`, while Hugo configuration, presentation bytes and inventories, and the PaperMod gitlink are compared with the reviewed `presentationCapturedFrom` Git tree. The only configuration exception is the exact approved deployment migration documented below. It does not access the network and uses only Python's standard library, Git, and the locally installed Hugo executable.

The real preservation render calls the same `scripts/build_site.py` build function
used for deployment. Consequently its fixed clock, `--buildFuture`, production
environment, fresh isolated cache, `--ignoreCache`, `SOURCE_DATE_EPOCH`, UTC
timezone, and fixed locale cannot drift into a second validator-specific command.
Command-capture tests enforce that shared contract.

## Approved Personal-Blog deployment baseURL migration

The user explicitly approved repairing preservation validation for the project
Pages deployment, without disabling safeguards. Commit
`00cca67fc70865897f3cbeaf6e41e33dd1e64bc3` already makes the sole approved
`hugo.toml` change:

```diff
-baseURL = 'https://build4me2.github.io/'
+baseURL = 'https://build4me2.github.io/Personal-Blog/'
```

The former root deployment emitted stylesheet URLs outside the project's Pages
mount, causing CSS 404s. This approval authorizes only that exact line change,
not a general configuration reconciliation mechanism or a new design baseline.
`capturedFrom` remains immutable at
`8daa5220b19ec7e529d4354c77707bb882c9bce3`; `presentationCapturedFrom`, review
records, and all baseline values (including the historical baseURL and config
hash) remain unchanged.

`validate_preservation_baseline.py` gates the migration on the original complete
config SHA-256
`a9d61d10a4335f70f07a0aa297499f43bb804e2cfd2cb33b86fec646f4ba0396`.
The protected-file check recognizes the migrated bytes only when reversing the
exact line restores that digest. The independent Git-history check applies the
same exact forward migration to the captured bytes and requires byte equality.
The setting check requires the approved new baseURL, so a rollback to the old
root URL also fails. Every other config byte, including settings outside the
dotted-settings inventory, remains protected even if editable hashes/settings
are rewritten. No content, citation, theme, template, CSS, layout, or build pin
exception is introduced.

Established baseline routes remain site-relative identities (`/<slug>/`), and
Hugo still writes `<slug>/index.html` within the artifact. Both rendered listing
and deployment-route validation resolve browser URLs against the approved
`https://build4me2.github.io/Personal-Blog/` mount before comparing those
identities. They require the exact origin and prefix boundary: old root links,
wrong hosts, wrong prefixes, and query/fragment substitutions cannot satisfy an
established listing entry. They do not blindly remove a path component.
`verify_built_routes.py` also requires local stylesheet links on home and every
established article and maps each URL within that mount to a nonempty `.css`
file inside the artifact. Only the exact existing Google Fonts stylesheet URL
from the protected `layouts/partials/extend_head.html` is exempt from local file
mapping; it cannot substitute for the built theme CSS. No network or live
deployment is needed.

Regression coverage lives in `tests/test_base_url_migration.py`,
`tests/test_preservation_validator.py`, and `tests/test_built_routes.py`.
It covers the unchanged captured inventory, approved migration, rejected root
rollback/other baseURLs, unrelated config mutations (also with rewritten
baselines), prefixed listing URLs, and missing/empty/out-of-mount CSS. A real
pinned Hugo build checks stylesheet URLs and all four prefixed article links.
Validate this migration with `make setup`, `make validate`, `make reproducible`,
`make build`, and `make verify-routes`; none of these pushes or deploys the site.

## Change policy

Essay editing and reconciliation are deliberately different:

- **Prohibited:** changing an essay's argument or wording, established route identity, typography, layout, colors, post-list design, header/footer behavior, or current PaperMod light/dark behavior.
- **Potentially approvable reconciliation:** correcting front matter or a citation destination while preserving the argument and design. Approval is not implied merely by regenerating a hash.

Before changing a citation destination, add a `citation-reconciliation` entry to `tests/baselines/review-records.json` containing:

1. a unique non-empty `id`;
2. `article`, the repository-relative post path;
3. `citationIndex`, the destination's one-based position (repeats therefore remain unambiguous);
4. exact, non-empty, differing `before` and `after` destinations;
5. a non-whitespace `reason` and `verificationEvidence` array;
6. `proseArgumentRoutePresentationUnchanged: true`.

For an approved front-matter correction, use a `front-matter-reconciliation` entry with the same `id`, `article`, `reason`, `verificationEvidence`, and unchanged-invariant flag, plus `field` and exact scalar `before` and `after` values. The only reconcilable fields are `date`, `draft`, `hideSummary`, and `ShowToc`; established titles and slugs/routes remain identities and cannot be reconciled. A date correction must also be reflected in the home-listing baseline derived from it. Unreviewed presentation and Hugo configuration changes remain prohibited. The existing `presentation-migration` record anchors the reviewed design; the single approved baseURL exception above does not authorize any further configuration or presentation change.

Then update only the affected source and fixture values in `preservation.json`, run the full validator, and include the post, review record, and baseline in review. Each changed value must consume an exact matching record; stale, duplicate, non-matching, or unknown-article records fail validation. Prose is compared directly with the inherited `capturedFrom` source after only hyperlink destinations are masked, so rebaselining hashes cannot authorize changed wording or arguments. Never update baseline hashes to make an unexplained content or design change pass. The initial record identifies the inherited commit used for this inventory and approves no changes.
