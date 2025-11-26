#!/usr/bin/env python3

import argparse
import json
import os

from random_composition_generator import (
    load_library,
    build_composition_and_bundle,
    normalize_patient_refs_in_bundle,
    structural_validate_bundle
)

def main():

    parser = argparse.ArgumentParser(description="Generate randomized FHIR Composition bundles.")
    parser.add_argument("--count", type=int, default=1,
                        help="Number of synthetic compositions to generate")
    parser.add_argument("--use-synthetic", action="store_true", default=False,
                        help="Generate a synthetic patient for each bundle (default: reuse existing Patient from library if available).")
    parser.add_argument("--canonical-patient", type=str, default=None,
                        help="If provided, normalize all Patient/* references to this Patient/<id> in the produced bundle.")
    parser.add_argument("--map-file", type=str, default=None,
                        help="Optional JSON file with mapping old_ref -> new_ref to apply to bundle before saving.")
    parser.add_argument("--randomize-values", action="store_true", default=False,
                        help="If set, synthesize randomized vital signs and basic lab observations and include them in the bundle.")

    args = parser.parse_args()

    count = args.count
    print(f"=== Generating {count} composition bundle(s) ===")

    # Try to load library from input_data; generator will still function without it
    resources_by_key, index_by_type, compositions_list = load_library("input_data")

    print(f"Loaded {len(resources_by_key)} resources from input_data.")

    for i in range(count):
        print(f"\n=== Generating bundle {i+1}/{count} ===")
        # generator returns (composition, bundle, output_file)
        composition, bundle, output_file = build_composition_and_bundle(
            resources_by_key,
            index_by_type,
            compositions_list,
            use_synthetic=args.use_synthetic,
            randomize_values=args.randomize_values
        )

        # apply mapping if requested
        if args.map_file and os.path.exists(args.map_file):
            with open(args.map_file, "r", encoding="utf-8") as fh:
                mapping = json.load(fh)
            normalize_patient_refs_in_bundle(bundle, mapping=mapping)
            # overwrite output file with mapped bundle
            with open(output_file, "w", encoding="utf-8") as fh:
                json.dump(bundle, fh, indent=2, ensure_ascii=False)

        if args.canonical_patient:
            normalize_patient_refs_in_bundle(bundle, canonical=args.canonical_patient)
            with open(output_file, "w", encoding="utf-8") as fh:
                json.dump(bundle, fh, indent=2, ensure_ascii=False)

        # Run structural validation to detect issues
        issues = structural_validate_bundle(bundle)
        if issues:
            print("⚠ Structural validation issues found:")
            for it in issues:
                if isinstance(it, dict):
                    sev = it.get("severity", "")
                    det = it.get("detail", str(it))
                    print(f" - [{sev}] {det}")
                else:
                    print(" -", it)
        else:
            print("✔ No structural issues found by validator.")

        # Ensure bundle saved (in case mapping/validation changed it)
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as fh:
            json.dump(bundle, fh, indent=2, ensure_ascii=False)

        print(f"Saved → {output_file}")
        print(f"Composition ID → {composition.get('id')}")

if __name__ == "__main__":
    main()
