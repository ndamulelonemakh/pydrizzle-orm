# Releasing

## GitHub Actions in this repo

- `CI`: runs formatting, linting, tests, and distribution build checks
- `Publish`: publishes built artifacts to TestPyPI or PyPI using trusted publishing

## PyPI trusted publishing setup

Configure publishers in both PyPI and TestPyPI before running the workflow.

### PyPI

Create a trusted publisher for:

- Owner: `ndamulelonemakh`
- Repository: `pydrizzle-orm`
- Workflow name: `publish.yml`
- Environment name: `pypi`

### TestPyPI

Create a trusted publisher for:

- Owner: `ndamulelonemakh`
- Repository: `pydrizzle-orm`
- Workflow name: `publish.yml`
- Environment name: `testpypi`

## Release flow

### Test publish

Run the `Publish` workflow manually and choose `testpypi`.

### Production release

1. Bump version in `pyproject.toml`
2. Commit and tag the release:

```bash
git tag v0.1.0
git push origin main --tags
```

3. Create a GitHub Release for the tag and publish it
4. The `Publish` workflow will build and publish to PyPI automatically

## Local verification before release

```bash
make all
make build
```

## Notes

- No API tokens are required when trusted publishing is configured correctly
- The publish jobs require GitHub Actions environments named `pypi` and `testpypi`
- If you want approval gates, configure required reviewers on those environments
