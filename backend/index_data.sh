#!/bin/bash


# ====================== CONFIGURATION ===============================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
PROCESS_CHUNKER_DIR="$PROJECT_ROOT/process_data/dsm5_chunker"
INDEXING_DIR="$PROJECT_ROOT/process_data/"
PYTHON_CMD="python" 

# ====================== FUNTION LOG ===================================
log_info() {
  echo -e "${BLUE}[INFO]${NC} $1"
}
log_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}
log_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}
log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
  echo "Usage: $0 [OPTION]"
  echo ""
  echo "Options:"
  echo "--parse               Parse PDF thành raw chunks"
  echo "--process             Xử lý raw chunks (split, merge)"
  echo "--pipeline            Pipeline xử lý Dsm5"
  echo "--index-els           Indexing chunks vào ELS"
  echo "--delete-index-els    Xóa index name của ELS"
}

# 1. ============================ STEP PARSE PDF TO RAW CHUNKS=============================
step_parse() {
  log_info "======================================="
  log_info "STEP 1: Parsing PDF -> Raw Chunks..."
  log_info "======================================="

  cd "$PROCESS_CHUNKER_DIR"
  $PYTHON_CMD parser.py 
  if [[ $? -eq 0 ]]; then
      log_success "Parse hoàn tất!"
  else
      log_error "Parse thất bại!"
      exit 1
  fi
}

# 2. =========================== STEP PROCESSING RAW CHUNKS ============================
step_process() {
  log_info "======================================="
  log_info "STEP 2: Processing Raw Chunks..."
  log_info "======================================="

  cd "$PROCESS_CHUNKER_DIR"
  $PYTHON_CMD processor.py
  if [[ $? -eq 0 ]]; then
    log_success "Processing hoàn tất!"
  else
    log_error "Processing thất bại!"
    exit 1
  fi
}

# 3. =========================== INdexing chunks to ELS ============================
index_elastic() {
  log_info "==========================================="
  log_info "STEP 3: Indexing chunks to Elasticsearch..."
  log_info "==========================================="

  cd "$INDEXING_DIR"
  $PYTHON_CMD index_elastic.py --index
  if [[ $? -eq 0 ]]; then
    log_success "Indexing to Els hoàn tất"
  else
    log_error "Indexing to Els thất bại"
    exit 1
  fi
}

# 4. ======================= Optional: Delete index name ELS ========================
delete_index_els() {
  log_info "==========================================="
  log_info "Delete index name of Elasticsearch..."
  log_info "==========================================="

  cd "$INDEXING_DIR"
  $PYTHON_CMD index_elastic.py --delete
  if [[ $? -eq 0 ]]; then
    log_success "Xóa index name ELS hoàn tất"
  else
    log_error "Xóa index name ELS thất bại"
    exit 1
  fi
}

# ================================ ENTRY POINT =======================================
case "${1:-}" in 
  --parse)
    step_parse
    ;;
  --process)
    step_process
    ;;
  --pipeline)
    step_parse
    step_process
    ;;
  --index-els)
    index_elastic
    ;;
  --delete-index-els)
    delete_index_els
    ;;
  --help)
    show_help
    ;;
esac


