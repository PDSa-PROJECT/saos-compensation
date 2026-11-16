# Contributing

## Commit messages and pull request titles

Use [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/) for new commit messages and pull request titles:

```text
<type>[optional scope][!]: <description>
```

Use a lowercase type from the following list and a concise, nonempty English description:

| Type | Use for |
|---|---|
| `feat` | New functionality |
| `fix` | Bug fixes |
| `refactor` | Internal restructuring without changing functionality |
| `docs` | Documentation and repository instructions |
| `test` | Test additions or corrections |
| `ci` | Continuous integration workflows |
| `build` | Dependencies, packaging and build tooling |
| `perf` | Performance improvements |
| `style` | Formatting-only changes |
| `chore` | Maintenance not covered by another type |
| `revert` | Reverting an earlier change |

A scope is optional and identifies the affected component, such as `settings`, `acquisition`, `extraction`, `embeddings` or `preprocessing`. Scopes are not restricted to that list. Use imperative descriptions, for example "add" rather than "added".

Examples:

```text
docs: adopt Conventional Commits
refactor(settings): introduce typed settings without changing behavior
fix(acquisition): preserve progress after an interrupted write
ci: validate pull request titles
```

Mark breaking changes with `!` before the colon or a `BREAKING CHANGE: <explanation>` footer in the commit body. A breaking change in a pull request must be marked with `!` in its title so that the title communicates the change without relying on the body:

```text
feat(storage)!: change the exported record schema
```

The pull request title describes the complete change, not an individual implementation step. When squash-merging, use the Conventional Commit pull request title as the squash commit subject. Git-generated merge commit messages are exempt; do not rewrite existing history just to apply this convention.

## Enforcement

The `PR title` GitHub Actions check validates the title format and allowed types for all pull requests, including stacked PRs. It runs on creation, title edits, reopening, new commits and transitions from draft to ready for review. The check validates syntax, not whether the description is English or imperative. It reads the event payload without checking out or executing PR code. No commit hooks, release automation or repository protection changes are introduced here; requiring the check for merging is a separate GitHub protection setting.

## Project guidance

Read `PROJECT.md` for the current functionality and configuration contract, `AGENTS.md` for engineering rules, and `STATUS.md` for completed work and remaining tasks. Keep changes focused, preserve existing artifacts, and document behavior changes in the relevant existing sections.
