How to contribute to Ambuda
===========================

Thank you for your interest in contributing to Ambuda! Ambuda is expanding
rapidly, and we're grateful for all the help we can get to complete this
ambitious project.

This doc will show you how you can contribute to Ambuda's technical work.


Reporting an issue
------------------

Create a GitHub issues for any *technical* bugs or issues you see while using
Ambuda. Please don't report errors on the text or parse data here.


Submitting patches
------------------

We use GitHub issues to track our technical work. If there isn't an open issue
for what you want to work on, create an issue so that we can discuss it first.

You can claim any issue that doesn't have an open PR or a core team member
assigned to it. No need to ask if you can work on it -- just go ahead.

Patch standards:

- Format your code with `black`.

  On Linux and OS X, you can enable the included pre-commit hook to automate this:
  ```bash
  ln -snfr infra/pre-commit .git/hooks/pre-commit
  ```

- Include tests if you're changing code. Your tests should succeed with your
  patch and fail without it.

- Update any relevant docs and docstrings.

- Your PR should contain a single commit that follows the style described
  [here][tpope].

[tpope]: https://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html

### Submitting a PR

- Fork from https://github.com/ambuda-org/ambuda/

- Make code changes and commit

- Submit a PR to `fork-landing` upstream branch.

- Wait for reviewers to comment or merge.

### Setting up your dev environment

Our [technical documentation][docs] will help you build Ambuda on your local
machine and run routine development tasks like testing and linting.

[docs]: https://ambuda.readthedocs.io/en/latest/
