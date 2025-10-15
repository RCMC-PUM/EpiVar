#!/bin/bash
set -e  # exit on first error

# Check if gene_sets_dir is set
if [ -z "$GENE_SETS_DIR" ]; then
  echo "Environment variable GENE_SETS_DIR is not set."
  exit 1
fi

echo "Step 1: Importing ontologies..."
poetry run python manage.py import_ontologies

echo "Step 2: Importing Human Reference Atlas..."
poetry run python manage.py import_human_reference_atlas

echo "Step 3: Importing reference..."
poetry run python manage.py import_reference

echo "Step 4: Importing chain files..."
poetry run python manage.py import_chain_files

echo "Step 5: Importing gene sets from directory: $GENE_SETS_DIR ..."
poetry run python manage.py import_gene_sets --dir "$GENE_SETS_DIR"

echo "Step 6: Importing SCREEN..."
poetry run python manage.py import_screen

echo "Step 7: Importing Epigenomic Roadmap..."
poetry run python manage.py import_epigenomic_roadmap

echo "All import steps completed successfully!"