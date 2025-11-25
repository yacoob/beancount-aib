# show action chooser
default:
  @just --choose

lint:
    uvx ruff check $(git ls-files "*.py")
    uvx basedpyright $(git ls-files "*.py")

test:
    uv run pytest -vvv --cov

continuous-test:
  watchexec -r -e py --shell=none just test
