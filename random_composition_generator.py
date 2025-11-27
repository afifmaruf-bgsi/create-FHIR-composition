#!/usr/bin/env python3
"""
random_composition_generator.py

- Default: uses synthetic patient
- Adds randomized vitals & basic labs when randomize_values=True
- Ensures all Patient/* references in included resources are normalized to the synthetic patient
- Returns (composition, bundle, output_file)
- Fixed section & entry limits (Option A)
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

# ---- Section & Entry Limits (Option A) ----
MIN_SECTIONS = 1
MAX_SECTIONS = 10
MIN_ENTRIES_PER_SECTION = 1
MAX_ENTRIES_PER_SECTION = 10

REF_RE = re.compile(r"([A-Za-z]+)\/([A-Za-z0-9\-\._]+)$")

def get_output_filename():
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return f"{OUTPUT_FOLDER}/bundle_{timestamp}.json"


# -------------------------
# Library loading utilities
# -------------------------
def load_library(folder, prefix=INPUT_PREFIX):
    resources_by_key = {}
    index_by_type = {}
    compositions_list = []

    if not os.path.exists(folder):
        return resources_by_key, index_by_type, compositions_list

    files = [f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(".json")]
    for fname in files:
        path = os.path.join(folder, fname)
        with open(path, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except Exception as e:
                print(f"Warning: cannot parse {fname}: {e}")
                continue

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


# -------------------------
# Synthetic Patient helper
# -------------------------
def generate_synthetic_patient():
    pid = "P"+str(uuid.uuid4())
    return {
        "resourceType": "Patient",
        "id": pid,
        "name": [{
            "use": "official",
            "family": f"Synthetic-{pid[:8]}",
            "given": ["Patient"]
        }],
        "gender": random.choice(["male", "female", "unknown"]),
        "birthDate": f"{random.randint(1940, 2005)}-01-01",
        "identifier": [
            {"system": "urn:synthetic", "value": pid}
        ]
    }


# -------------------------
# Vitals & Labs utilities
# -------------------------
def _random_range(mean, std, clamp_min=None, clamp_max=None):
    val = random.gauss(mean, std)
    if clamp_min is not None:
        val = max(clamp_min, val)
    if clamp_max is not None:
        val = min(clamp_max, val)
    # round sensibly
    if abs(val) >= 100:
        return int(round(val))
    return round(val, 1)

def generate_vitals_observations(synthetic_patient_ref, encounter_ref=None, timestamp=None):
    ts = timestamp or datetime.utcnow().isoformat() + "Z"
    obs = []
    # Heart rate
    hr = _random_range(72, 8, 40, 180)
    obs.append({
        "resourceType":"Observation",
        "id": str(uuid.uuid4()),
        "status":"final",
        "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"vital-signs","display":"Vital Signs"}]}],
        "code":{"coding":[{"system":"http://loinc.org","code":"8867-4","display":"Heart rate"}],"text":"Heart rate"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": hr, "unit":"beats/minute", "system":"http://unitsofmeasure.org", "code":"{beats}/min"}
    })
    # Respiratory rate
    rr = _random_range(16, 3, 6, 40)
    obs.append({
        "resourceType":"Observation",
        "id": str(uuid.uuid4()),
        "status":"final",
        "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"vital-signs"}]}],
        "code":{"coding":[{"system":"http://loinc.org","code":"9279-1","display":"Respiratory rate"}],"text":"Respiratory rate"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": rr, "unit":"breaths/min", "system":"http://unitsofmeasure.org", "code":"breaths/min"}
    })
    # Blood pressure panel
    sys_bp = _random_range(120, 12, 70, 240)
    dia_bp = _random_range(78, 8, 40, 140)
    obs.append({
        "resourceType":"Observation",
        "id": str(uuid.uuid4()),
        "status":"final",
        "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"vital-signs"}]}],
        "code":{"coding":[{"system":"http://loinc.org","code":"85354-9","display":"Blood pressure panel"}],"text":"Blood pressure"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "component":[
            {"code":{"coding":[{"system":"http://loinc.org","code":"8480-6","display":"Systolic blood pressure"}],"text":"Systolic BP"},
             "valueQuantity":{"value": sys_bp, "unit":"mmHg","system":"http://unitsofmeasure.org","code":"mm[Hg]"}},
            {"code":{"coding":[{"system":"http://loinc.org","code":"8462-4","display":"Diastolic blood pressure"}],"text":"Diastolic BP"},
             "valueQuantity":{"value": dia_bp, "unit":"mmHg","system":"http://unitsofmeasure.org","code":"mm[Hg]"}}
        ]
    })
    # Temperature
    temp = _random_range(36.6, 0.4, 34.0, 42.0)
    obs.append({
        "resourceType":"Observation",
        "id": str(uuid.uuid4()),
        "status":"final",
        "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"vital-signs"}]}],
        "code":{"coding":[{"system":"http://loinc.org","code":"8310-5","display":"Body temperature"}],"text":"Body temperature"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": temp, "unit":"Cel","system":"http://unitsofmeasure.org","code":"Cel"}
    })
    # SpO2
    spo2 = _random_range(98, 1.5, 80, 100)
    obs.append({
        "resourceType":"Observation",
        "id": str(uuid.uuid4()),
        "status":"final",
        "category":[{"coding":[{"system":"http://terminology.hl7.org/CodeSystem/observation-category","code":"vital-signs"}]}],
        "code":{"coding":[{"system":"http://loinc.org","code":"2708-6","display":"Oxygen saturation in Arterial blood by Pulse oximetry"}],"text":"SpO2"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": spo2, "unit":"%","system":"http://unitsofmeasure.org","code":"%"}
    })
    if encounter_ref:
        for o in obs:
            o["encounter"] = {"reference": encounter_ref}
    return obs

def generate_basic_lab_observations(synthetic_patient_ref, timestamp=None):
    ts = timestamp or datetime.utcnow().isoformat() + "Z"
    labs = []
    # Hemoglobin g/dL
    hgb = _random_range(13.5, 1.2, 6, 20)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"718-7","display":"Hemoglobin [Mass/volume] in Blood"}],"text":"Hemoglobin"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": hgb, "unit":"g/dL","system":"http://unitsofmeasure.org","code":"g/dL"}
    })
    # WBC x10^9/L
    wbc = _random_range(7.0, 2.5, 1.0, 30.0)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"6690-2","display":"Leukocytes [#/volume] in Blood by Automated count"}],"text":"WBC"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": wbc, "unit":"10^9/L","system":"http://unitsofmeasure.org","code":"10*9/L"}
    })
    # Platelets x10^9/L
    plt = _random_range(250, 60, 50, 700)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"777-3","display":"Platelets [#/volume] in Blood by Automated count"}],"text":"Platelets"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": plt, "unit":"10^9/L","system":"http://unitsofmeasure.org","code":"10*9/L"}
    })
    # Sodium mmol/L
    na = _random_range(140, 3, 120, 160)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"2951-2","display":"Sodium [Moles/volume] in Serum or Plasma"}],"text":"Sodium"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": na, "unit":"mmol/L","system":"http://unitsofmeasure.org","code":"mmol/L"}
    })
    # Potassium mmol/L
    k = _random_range(4.1, 0.4, 2.5, 7.0)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"2823-3","display":"Potassium [Moles/volume] in Serum or Plasma"}],"text":"Potassium"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": k, "unit":"mmol/L","system":"http://unitsofmeasure.org","code":"mmol/L"}
    })
    # Creatinine mg/dL
    cr = _random_range(0.95, 0.25, 0.2, 10.0)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"2160-0","display":"Creatinine [Mass/volume] in Serum or Plasma"}],"text":"Creatinine"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": cr, "unit":"mg/dL","system":"http://unitsofmeasure.org","code":"mg/dL"}
    })
    # Glucose mg/dL
    glu = _random_range(98, 20, 40, 400)
    labs.append({
        "resourceType":"Observation","id":str(uuid.uuid4()),"status":"final",
        "code":{"coding":[{"system":"http://loinc.org","code":"2345-7","display":"Glucose [Mass/volume] in Blood"}],"text":"Glucose"},
        "subject":{"reference": synthetic_patient_ref},
        "effectiveDateTime": ts,
        "valueQuantity":{"value": glu, "unit":"mg/dL","system":"http://unitsofmeasure.org","code":"mg/dL"}
    })
    return labs


# -------------------------
# Core bundle construction
# -------------------------
def find_reference_strings(obj):
    refs = set()
    def _walk(o):
        if isinstance(o, dict):
            if "reference" in o and isinstance(o["reference"], str):
                m = REF_RE.search(o["reference"])
                if m:
                    refs.add((m.group(1), m.group(2)))
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

def _normalize_patient_refs_in_resource(obj, synthetic_patient_ref):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "reference" and isinstance(v, str) and v.startswith("Patient/"):
                obj[k] = synthetic_patient_ref
            elif isinstance(v, str) and v.startswith("Patient/"):
                obj[k] = synthetic_patient_ref
            else:
                _normalize_patient_refs_in_resource(v, synthetic_patient_ref)
    elif isinstance(obj, list):
        for item in obj:
            _normalize_patient_refs_in_resource(item, synthetic_patient_ref)

def include_resource_and_children(bundle, resources_by_key, key, bundle_fullUrls, synthetic_patient_ref=None):
    if key not in resources_by_key:
        return
    res = resources_by_key[key]
    fullUrl = f"{res['resourceType']}/{res['id']}"
    if fullUrl in bundle_fullUrls:
        return
    import copy
    res_copy = copy.deepcopy(res)
    if synthetic_patient_ref:
        _normalize_patient_refs_in_resource(res_copy, synthetic_patient_ref)
    bundle["entry"].append({"fullUrl": fullUrl, "resource": res_copy})
    bundle_fullUrls.add(fullUrl)
    refs = find_reference_strings(res_copy)
    for rtype, rid in refs:
        child_key = (rtype, rid)
        if child_key in resources_by_key:
            include_resource_and_children(bundle, resources_by_key, child_key, bundle_fullUrls, synthetic_patient_ref)


def build_composition_and_bundle(resources_by_key, index_by_type, compositions_list, use_synthetic=True, randomize_values=False):
    """
    Returns: (composition, bundle, output_file)
    - By default uses synthetic patient (use_synthetic param kept for backwards compatibility)
    - randomize_values=True adds vitals & basic labs as Observations associated with the synthetic patient
    """
    # pick a composition template if present
    composition_template = random.choice(compositions_list) if compositions_list else None

    synthetic_patient = generate_synthetic_patient()
    synthetic_patient_ref = f"Patient/{synthetic_patient['id']}"

    # Build composition
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
        "title": f"Synthetic Composition Document ({datetime.utcnow().isoformat()}Z)",
        "date": datetime.utcnow().isoformat() + "Z",
        "author": [{"display": "SyntheticGenerator"}],
        "subject": {"reference": synthetic_patient_ref},
        "section": []
    }

    # Build sections from template or create placeholders
    selected_keys = set()
    composition_sections = []

    if composition_template and "section" in composition_template:
        template_sections = composition_template.get("section", [])

        # Pick N sections
        n_sections = random.randint(MIN_SECTIONS, MAX_SECTIONS)
        selected_sections = random.sample(
            template_sections,
            min(len(template_sections), n_sections)
        )

        for sec in selected_sections:
            entries = []

            # pick entries
            template_entries = sec.get("entry", [])
            n_entries = random.randint(MIN_ENTRIES_PER_SECTION, MAX_ENTRIES_PER_SECTION)
            selected_entries = random.sample(
                template_entries,
                min(len(template_entries), n_entries)
            )

            for e in selected_entries:
                if isinstance(e, dict) and "reference" in e:
                    ref = e["reference"]
                    m = REF_RE.search(ref)
                    if m:
                        rtype, rid = m.group(1), m.group(2)
                        key = (rtype, rid)
                        entries.append({"reference": f"{rtype}/{rid}"})
                        selected_keys.add(key)

            if entries:
                composition_sections.append({
                    "title": sec.get("title", "Section"),
                    "entry": entries
                })

    else:
        # fallback if template doesn't have sections
        composition_sections.append({
            "title": "Synthetic Episode",
            "entry": [{"reference": f"Encounter/{str(uuid.uuid4())}"}]
        })
        composition_sections.append({
            "title": "Synthetic Observations",
            "entry": [{"reference": f"Observation/{str(uuid.uuid4())}"}]
        })

    composition["section"] = composition_sections

    # Build bundle with composition and synthetic patient
    bundle = {
        "resourceType": "Bundle",
        "type": "document",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": [
            {"fullUrl": f"Composition/{composition['id']}", "resource": composition},
            {"fullUrl": synthetic_patient_ref, "resource": synthetic_patient}
        ]
    }
    bundle_fullUrls = set([f"Composition/{composition['id']}", synthetic_patient_ref])

    # include referenced resources from library or placeholders
    for key in list(selected_keys):
        if key in resources_by_key:
            include_resource_and_children(bundle, resources_by_key, key, bundle_fullUrls, synthetic_patient_ref)
        else:
            rtype, rid = key
            placeholder = {"resourceType": rtype, "id": rid}
            if rtype in ("Observation", "Procedure", "Encounter", "Specimen", "ServiceRequest", "ImagingStudy", "DiagnosticReport"):
                placeholder["subject"] = {"reference": synthetic_patient_ref}
            bundle["entry"].append({"fullUrl": f"{rtype}/{rid}", "resource": placeholder})
            bundle_fullUrls.add(f"{rtype}/{rid}")

    # Optionally generate vitals & labs
    if randomize_values:
        # try to find an Encounter to associate with observations
        encounter_ref = None
        for e in bundle.get("entry", []):
            r = e.get("resource", {})
            if r.get("resourceType") == "Encounter":
                encounter_ref = f"Encounter/{r.get('id')}"
                break
        vitals = generate_vitals_observations(synthetic_patient_ref, encounter_ref=encounter_ref)
        for v in vitals:
            full = f"Observation/{v['id']}"
            if full not in bundle_fullUrls:
                bundle['entry'].append({'fullUrl': full, 'resource': v})
                bundle_fullUrls.add(full)

        labs = generate_basic_lab_observations(synthetic_patient_ref)
        for l in labs:
            full = f"Observation/{l['id']}"
            if full not in bundle_fullUrls:
                bundle['entry'].append({'fullUrl': full, 'resource': l})
                bundle_fullUrls.add(full)

    # Normalize any Patient refs inside the bundle to the synthetic patient
    _normalize_patient_refs_in_resource(bundle, synthetic_patient_ref)

    # Ensure references in composition sections are present (create placeholders if needed)
    for sec in composition["section"]:
        for e in sec.get("entry", []):
            m = REF_RE.search(e["reference"])
            if m:
                fullUrl = f"{m.group(1)}/{m.group(2)}"
                if fullUrl not in bundle_fullUrls:
                    key = (m.group(1), m.group(2))
                    if key in resources_by_key:
                        include_resource_and_children(bundle, resources_by_key, key, bundle_fullUrls, synthetic_patient_ref)
                    else:
                        placeholder = {"resourceType": m.group(1), "id": m.group(2)}
                        if m.group(1) in ("Observation","Procedure","Encounter","Specimen","ServiceRequest","ImagingStudy","DiagnosticReport"):
                            placeholder["subject"] = {"reference": synthetic_patient_ref}
                        bundle["entry"].append({"fullUrl": fullUrl, "resource": placeholder})
                        bundle_fullUrls.add(fullUrl)

    # final normalization pass (defensive)
    _normalize_patient_refs_in_resource(bundle, synthetic_patient_ref)

    # write to file
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    out_file = get_output_filename()
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump(bundle, fh, indent=2, ensure_ascii=False)

    return composition, bundle, out_file


# -------------------------
# Mapping & validation utils
# -------------------------
def normalize_patient_refs_in_bundle(bundle, mapping=None, canonical=None):
    if mapping is None and canonical is None:
        return bundle
    def _walk(o):
        if isinstance(o, dict):
            for k,v in list(o.items()):
                if k == "reference" and isinstance(v, str) and v.startswith("Patient/"):
                    if mapping and v in mapping:
                        o[k] = mapping[v]
                    elif canonical:
                        o[k] = canonical
                else:
                    _walk(v)
        elif isinstance(o, list):
            for item in o:
                _walk(item)
    _walk(bundle)
    return bundle

def structural_validate_bundle(bundle):
    issues = []
    present = set()
    entries = bundle.get("entry", [])
    for e in entries:
        full = e.get("fullUrl")
        res = e.get("resource")
        if full:
            present.add(full)
        elif res and "resourceType" in res and "id" in res:
            present.add(f"{res['resourceType']}/{res['id']}")
        else:
            issues.append({"severity":"error","detail":"entry with no fullUrl and no resource id"})

    comp = None
    for e in entries:
        if e.get("resource",{}).get("resourceType") == "Composition":
            comp = e["resource"]
            break

    if not comp:
        issues.append({"severity":"error","detail":"No Composition in Bundle"})
    else:
        subj = comp.get("subject",{}).get("reference")
        if not subj:
            issues.append({"severity":"error","detail":"Composition.subject missing"})
        else:
            if subj not in present:
                issues.append({"severity":"error","detail":f"Composition.subject {subj} not present as resource in bundle"})
            else:
                if not subj.startswith("Patient/"):
                    issues.append({"severity":"warning","detail":f"Composition.subject {subj} is not a Patient reference"})

    # check composition.section references
    if comp:
        for sec in comp.get("section",[]):
            for e in sec.get("entry",[]):
                ref = e.get("reference")
                if ref and ref not in present:
                    issues.append({"severity":"error","detail":f"Reference {ref} in composition.section not present in bundle"})

    # check patient refs inside resources point to present patient
    for e in entries:
        res = e.get("resource")
        if isinstance(res, dict):
            def _walk(o):
                if isinstance(o, dict):
                    for k,v in o.items():
                        if k == "reference" and isinstance(v, str) and v.startswith("Patient/"):
                            if v not in present:
                                issues.append({"severity":"error","detail":f"Patient reference {v} in resource {res.get('resourceType')}/{res.get('id')} not present in bundle"})
                        else:
                            _walk(v)
                elif isinstance(o, list):
                    for it in o:
                        _walk(it)
            _walk(res)
    return issues


# Script entrypoint
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=False, default=None)
    parser.add_argument("--randomize-values", action="store_true", default=False,
                        help="If set, generate vitals & lab observations for synthetic patient.")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as fh:
        b = json.load(fh)

    resources_by_key = {}
    index_by_type = {}
    compositions_list = []

    for entry in b.get("entry",[]):
        res = entry.get("resource")
        if not res or "resourceType" not in res:
            continue
        rtype = res["resourceType"]
        rid = res.get("id") or str(uuid.uuid4())
        res["id"] = rid
        key = (rtype, rid)
        resources_by_key[key] = res
        index_by_type.setdefault(rtype, []).append(key)
        if rtype == "Composition":
            compositions_list.append(res)

    comp, new_bundle, out_file = build_composition_and_bundle(resources_by_key, index_by_type, compositions_list, use_synthetic=True, randomize_values=args.randomize_values)
    if args.output:
        out_file = args.output
        with open(out_file, "w", encoding="utf-8") as fh:
            json.dump(new_bundle, fh, indent=2, ensure_ascii=False)
    print("Wrote:", out_file)
