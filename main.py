#!/usr/bin/env python3

from random_composition_generator import (
    load_library,
    build_composition_and_bundle,
    LIB_FOLDER,
    OUTPUT_FOLDER
)
import json
import os

def main():

    print("=== STEP 1: Load Resource Library ===")
    print(f"Reading baseline compositions from folder: {LIB_FOLDER}")

    resources_by_key, index_by_type, compositions_list = load_library(LIB_FOLDER)

    print("\n=== STEP 2: Generate Randomized FHIR Composition Bundle ===")
    composition, bundle, missing_refs, output_file = build_composition_and_bundle(
        resources_by_key,
        index_by_type,
        compositions_list
    )

    if missing_refs:
        print("\n⚠ Missing referenced resources (not found in library):")
        for ref in missing_refs:
            print(" -", ref)
    else:
        print("\nAll referenced resources resolved successfully.")

    print("\n=== STEP 3: Output Saved ===")
    print(f"📄 File written to: {output_file}")

    print(f"\nComposition ID: {composition['id']}")
    print(f"Sections: {len(composition.get('section', []))}")

    for sec in composition.get("section", []):
        print(f"  - {sec['title']}: {len(sec.get('entry', []))} entries")


if __name__ == "__main__":
    main()
