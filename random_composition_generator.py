#!/usr/bin/env python3
"""
build_random_composition_bundle_recursive.py

Generates a randomized FHIR Composition document Bundle using:
- Real clinical section templates (Option B)
- Randomized sections and entries
- Recursive reference resolution

Reads composition bundles from:
    input_data/composition_*.json

Outputs bundle to:
    output/bundle_<timestamp>.json
"""

import json
import os
import random
import re
import uuid
from datetime import datetime

# Config
LIB_FOLDER = "input_data"
INPUT_PREFIX = "composition_"
OUTPUT_FOLDER = "output"

def get_output_filename():
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{OUTPUT_FOLDER}/bundle_{timestamp}.json"

MIN_SECTIONS = 3
MAX_SECTIONS = 7
MIN_ENTRIES_PER_SECTION = 1
MAX_ENTRIES_PER_SECTION = 5

# Section templates (Option B)
SECTION_TEMPLATES = [
    {"title": "Episode Perawatan", "allowed_types": ["EpisodeOfCare", "Encounter", "Condition"]},
    {"title": "Anamnesis", "allowed_types": ["Condition", "QuestionnaireResponse", "FamilyMemberHistory", "AllergyIntolerance", "MedicationStatement"]},
    {"title": "Pemeriksaan Fisik", "allowed_types": ["Observation"]},
    {"title": "Tanda Vital", "allowed_types": ["Observation"]},
    {"title": "Hasil Pemeriksaan Penunjang", "allowed_types": ["Observation", "DiagnosticReport", "Specimen", "Procedure"]},
    {"title": "Pemeriksaan Fungsional", "allowed_types": ["Observation", "ClinicalImpression"]},
    {"title": "Diagnosis", "allowed_types": ["Condition", "ClinicalImpression"]},
    {"title": "Tindakan/Prosedur Medis", "allowed_types": ["Procedure", "ActivityDefinition"]},
    {"title": "Obat", "allowed_types": ["MedicationRequest", "MedicationDispense", "MedicationAdministration", "MedicationStatement"]},
    {"title": "Rencana Tindak Lanjut", "allowed_types": ["CarePlan", "ServiceRequest"]},
    {"title": "Perjalanan Kunjungan Pasien", "allowed_types": ["Observation", "Procedure", "Encounter"]},
]

# Detect FHIR reference patterns such as "Observation/12345"
REF_RE = re.compile(r"([A-Za-z]+)\/([A-Za-z0-9\-\._]+)$")


# -----------------------------------------------------------
# Load baseline library
# -----------------------------------------------------------
def load_library(folder, prefix=INPUT_PREFIX):
    resources_by_key = {}
    index_by_type = {}
    compositions_list = []

    files = [f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(".json")]
    if not files:
        raise FileNotFoundError(f"No files starting with '{prefix}' found in {folder}")

    for fname in files:
        path = os.path.join(folder, fname)
        with open(path, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except Exception as e:
                print(f"Warning: cannot parse {fname}: {e}")
                continue

        # Case: full bundle
        if isinstance(data, dict) and data.get("resourceType") == "Bundle" and "entry" in data:
            for entry in data.get("entry", []):
                resource = entry.get("resource")
                if not resource or "resourceType" not in resource:
                    continue

                rtype = resource["resourceType"]
                rid = resource.get("id") or str(uuid.uuid4())
                resource["id"] = rid

                key = (rtype, rid)
                resources_by_key[key] = resource
                index_by_type.setdefault(rtype, []).append(key)

                if rtype == "Composition":
                    compositions_list.append(resource)

        # Case: single resource
        elif isinstance(data, dict) and "resourceType" in data:
            resource = data
            rtype = resource["resourceType"]
            rid = resource.get("id") or str(uuid.uuid4())
            resource["id"] = rid

            key = (rtype, rid)
            resources_by_key[key] = resource
            index_by_type.setdefault(rtype, []).append(key)

            if rtype == "Composition":
                compositions_list.append(resource)

        else:
            print(f"Unrecognized structure in {fname}")

    return resources_by_key, index_by_type, compositions_list


# -----------------------------------------------------------
# Choose subject, author, encounter
# -----------------------------------------------------------
def choose_subject_author_encounter(resources_by_key, index_by_type):
    subject_resource = author_resource = encounter_resource = None
    subject_ref = author_ref = encounter_ref = None

    if "Patient" in index_by_type:
        key = random.choice(index_by_type["Patient"])
        subject_resource = resources_by_key[key]
        subject_ref = f"Patient/{subject_resource['id']}"

    if "Practitioner" in index_by_type:
        key = random.choice(index_by_type["Practitioner"])
        author_resource = resources_by_key[key]
        author_ref = f"Practitioner/{author_resource['id']}"

    if "Encounter" in index_by_type:
        enc_keys = index_by_type["Encounter"]
        matching = []

        if subject_ref:
            for k in enc_keys:
                enc = resources_by_key[k]
                subj = enc.get("subject")
                if subj and isinstance(subj, dict) and subj.get("reference") == subject_ref:
                    matching.append(k)

        chosen = random.choice(matching) if matching else random.choice(enc_keys)
        encounter_resource = resources_by_key[chosen]
        encounter_ref = f"Encounter/{encounter_resource['id']}"

    return {
        "subject_ref": subject_ref,
        "subject_resource": subject_resource,
        "author_ref": author_ref,
        "author_resource": author_resource,
        "encounter_ref": encounter_ref,
        "encounter_resource": encounter_resource
    }


# -----------------------------------------------------------
# Recursive reference scanner
# -----------------------------------------------------------
def find_reference_strings(obj):
    refs = set()

    def _walk(o):
        if isinstance(o, dict):
            # reference field
            if "reference" in o and isinstance(o["reference"], str):
                m = REF_RE.search(o["reference"])
                if m:
                    refs.add((m.group(1), m.group(2)))

            # check all string fields
            for k, v in o.items():
                if isinstance(v, str):
                    m = REF_RE.search(v)
                    if m:
                        refs.add((m.group(1), m.group(2)))
                else:
                    _walk(v)

        elif isinstance(o, list):
            for item in o:
                _walk(item)

    _walk(obj)
    return refs


# -----------------------------------------------------------
# Random resource picking
# -----------------------------------------------------------
def pick_random_resources_for_section(allowed_types, index_by_type, count, resources_by_key, already_selected):
    candidates = []

    for rtype in allowed_types:
        for key in index_by_type.get(rtype, []):
            if key not in already_selected:
                candidates.append(key)

    if not candidates:
        return []

    chosen = random.sample(candidates, min(count, len(candidates)))
    result = []

    for key in chosen:
        res = resources_by_key[key]
        ref = f"{res['resourceType']}/{res['id']}"
        result.append((ref, res, key))

    return result


# -----------------------------------------------------------
# Build composition + bundle
# -----------------------------------------------------------
def build_composition_and_bundle(resources_by_key, index_by_type, compositions_list):

    selection = choose_subject_author_encounter(resources_by_key, index_by_type)
    subject_ref = selection["subject_ref"]
    subject_resource = selection["subject_resource"]
    author_ref = selection["author_ref"]
    author_resource = selection["author_resource"]
    encounter_ref = selection["encounter_ref"]
    encounter_resource = selection["encounter_resource"]

    # pick sections
    n_sections = random.randint(MIN_SECTIONS, MAX_SECTIONS)
    picked_templates = random.sample(SECTION_TEMPLATES, n_sections)

    selected_keys = set()
    composition_sections = []

    # build section contents
    for tmpl in picked_templates:
        title = tmpl["title"]
        num_entries = random.randint(MIN_ENTRIES_PER_SECTION, MAX_ENTRIES_PER_SECTION)

        picked = pick_random_resources_for_section(
            tmpl["allowed_types"], index_by_type, num_entries,
            resources_by_key, selected_keys
        )

        if not picked:
            continue

        entries = []
        for ref, res, key in picked:
            entries.append({"reference": ref})
            selected_keys.add(key)

        composition_sections.append({
            "title": title,
            "entry": entries
        })

    # fallback if empty
    if not composition_sections:
        any_key = next(iter(resources_by_key.keys()))
        r = resources_by_key[any_key]
        composition_sections.append({
            "title": "Generated Section",
            "entry": [{"reference": f"{r['resourceType']}/{r['id']}"}]
        })
        selected_keys.add(any_key)

    # create composition
    comp_id = f"generated-comp-{uuid.uuid4()}"
    composition = {
        "resourceType": "Composition",
        "id": comp_id,
        "status": "final",
        "type": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11506-3",
                "display": "Clinical Document"
            }]
        },
        "title": f"Randomized Composition Document ({datetime.utcnow().isoformat()}Z)",
        "date": datetime.utcnow().isoformat() + "Z",
        "author": [{"reference": author_ref}] if author_ref else [{"display": "AutoGenerator"}],
        "subject": {"reference": subject_ref} if subject_ref else None,
        "encounter": {"reference": encounter_ref} if encounter_ref else None,
        "section": composition_sections
    }

    # build bundle
    bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": [
            {"fullUrl": f"Composition/{composition['id']}", "resource": composition}
        ]
    }

    bundle_fullUrls = set([f"Composition/{composition['id']}"])

    # recursive include function
    def include_resource_by_key(key):
        if key not in resources_by_key:
            return

        res = resources_by_key[key]
        fullUrl = f"{res['resourceType']}/{res['id']}"

        if fullUrl in bundle_fullUrls:
            return

        bundle["entry"].append({"fullUrl": fullUrl, "resource": res})
        bundle_fullUrls.add(fullUrl)

        # scan for referenced resources recursively
        refs = find_reference_strings(res)
        for rtype, rid in refs:
            child_key = (rtype, rid)
            if child_key in resources_by_key:
                include_resource_by_key(child_key)

    # include primary resources
    if subject_resource:
        include_resource_by_key(("Patient", subject_resource["id"]))
    if author_resource:
        include_resource_by_key(("Practitioner", author_resource["id"]))
    if encounter_resource:
        include_resource_by_key(("Encounter", encounter_resource["id"]))

    for key in list(selected_keys):
        include_resource_by_key(key)

    # verify all composition entries resolve
    missing = []
    for sec in composition["section"]:
        for e in sec.get("entry", []):
            m = REF_RE.search(e["reference"])
            if m:
                fullUrl = f"{m.group(1)}/{m.group(2)}"
                if fullUrl not in bundle_fullUrls:
                    missing.append(fullUrl)

    # Save output
    output_file = get_output_filename()
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2, ensure_ascii=False)

    print(f"\nSaved randomized Composition Bundle to: {output_file}")

    return composition, bundle, missing, output_file


# -----------------------------------------------------------
# Script entry point
# -----------------------------------------------------------
def main():
    print("Loading resource library...")
    resources_by_key, index_by_type, compositions_list = load_library(LIB_FOLDER)

    print(f"Loaded {len(resources_by_key)} resources.")

    composition, bundle, missing, output_file = build_composition_and_bundle(
        resources_by_key, index_by_type, compositions_list
    )

    if missing:
        print("\n⚠ Missing referenced resources:")
        for m in missing:
            print(" -", m)
    else:
        print("\nAll references successfully resolved.")

    print("\nOutput saved to:", output_file)


if __name__ == "__main__":
    main()
