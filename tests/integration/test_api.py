from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["app_mode"] == "mock"


def test_enrich_single_end_to_end():
    r = client.post("/api/enrich-single", json={
        "part_desc": "PDSH4816AF Dishwasher SS - Display Only",
        "mfg_part_num": "PDSH4816AF",
        "part_manuf": "Appliance Dealers Cooperative (APPDE)",
    })
    assert r.status_code == 200
    data = r.json()
    assert data["manufacturer"]["canonical_value"] == "Rheem Manufacturing"
    assert data["output_record"]["BRAND_NAME"] == "FRIGIDAIRE®"
    assert len(data["output_record"]) == 252


def test_upload_process_download_flow(tmp_path):
    csv_content = (
        "Mfg_Part_Num,Part_Desc,E1_Brand,Unilog_Brand,DIB_Brand,Part_Manuf\n"
        'PDSH4816AF,"PDSH4816AF Dishwasher SS - Display Only",-- Unbranded --,-- No Unilog Brand --,-- No DIB Brand --,Appliance Dealers Cooperative (APPDE)\n'
    )
    f = tmp_path / "mini.csv"
    f.write_text(csv_content)

    with open(f, "rb") as fh:
        up = client.post("/api/upload", files={"file": ("mini.csv", fh, "text/csv")})
    assert up.status_code == 200
    upload_id = up.json()["upload_id"]

    proc = client.post(f"/api/process/{upload_id}")
    assert proc.status_code == 200
    assert proc.json()["summary"]["total"] == 1

    results = client.get(f"/api/results/{upload_id}")
    assert results.status_code == 200
    assert results.json()["total"] == 1

    dl = client.get(f"/api/download/{upload_id}?fmt=csv")
    assert dl.status_code == 200


def test_system_health_endpoint():
    r = client.get("/api/system-health")
    assert r.status_code == 200
    assert r.json()["manufacturer_master_rows"] > 0
