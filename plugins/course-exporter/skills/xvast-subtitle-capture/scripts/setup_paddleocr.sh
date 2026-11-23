#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
project_root="${PWD:A}"
conda_env=""
index_url="${PIP_INDEX_URL:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --conda-env)
      conda_env="${2:?--conda-env requires a name}"
      shift 2
      ;;
    --index-url)
      index_url="${2:?--index-url requires a URL}"
      shift 2
      ;;
    *)
      print -u2 -- "Unknown option: $1"
      exit 2
      ;;
  esac
done

run_python() {
  if [[ -n "$conda_env" ]]; then
    conda run --no-capture-output -n "$conda_env" python "$@"
  else
    "${project_root}/.venv/bin/python" "$@"
  fi
}

if [[ -z "$conda_env" && ! -x "${project_root}/.venv/bin/python" ]]; then
  python3 -m venv "${project_root}/.venv"
fi

pip_args=(-r "${script_dir}/paddleocr-requirements.txt")
if [[ -n "$index_url" ]]; then
  pip_args=(-i "$index_url" $pip_args)
fi
run_python -m pip install $pip_args

export PADDLE_PDX_CACHE_HOME="${PADDLE_PDX_CACHE_HOME:-${project_root}/.paddleocr-cache}"
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
run_python "${script_dir}/paddleocr_subtitles.py" --model-size mobile --setup-only --download-models
run_python "${script_dir}/paddleocr_subtitles.py" --model-size server --setup-only --download-models
run_python -m pip check

print -- "PaddleOCR ready (mobile primary + server fallback)"
print -- "Python environment: ${conda_env:-${project_root}/.venv}"
print -- "Model cache: ${PADDLE_PDX_CACHE_HOME}"
