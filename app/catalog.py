CATALOG = [
    ("lighting_level", "Volunteer night audit, manual 4-level category per segment", "measurement", "none", "inter-rater agreement across 2 auditors", "unchecked"),
    ("lighting_level", "Phone EXIF exposure to relative lux", "proxy", "none", "per-device calibration against a reference meter", "unchecked"),
    ("lamp_outage", "User-reported outage, reviewer-verified", "measurement", "user_optin", "none for the report; review process defined", "unchecked"),
    ("sightline_depth", "Ray-cast over OSM building footprints", "measurement", "none", "footprint completeness audit on a sample", "unchecked"),
    ("canopy_occlusion", "Human observation checklist (sky visible / partial / blocked)", "measurement", "none", "inter-rater agreement", "unchecked"),
    ("canopy_occlusion", "Sentinel-2 NDVI", "proxy", "none", "correlation study against the checklist; vegetation is not pedestrian sightline", "unchecked"),
    ("activity_level", "Opted-in anonymised traces, reported as opted-in activity sample with coverage", "proxy", "user_optin", "adoption and time-coverage study plus a published privacy model (k>=5 insufficient for longitudinal traces)", "unchecked"),
    ("walkability", "Audit checklist: footpath present / broken / absent", "measurement", "none", "inter-rater agreement", "unchecked"),
    ("open_poi_distance", "Observed opening hours of accessible public POIs", "measurement", "none", "access and entrance verification; no refuge guarantee", "unchecked"),
    ("dog_report_risk", "User reports with time-decay kernel", "measurement", "user_optin", "decay parameters are a product assumption", "unchecked"),
    ("network_signal", "Native app telephony reading", "measurement", "user_optin", "not reachable from a browser; needs a native client", "deferred"),
    ("waterlogging", "Scenario event or reviewed report", "report", "none", "street-level drainage accuracy unestablished", "deferred"),
    ("loitering_presence", "-", "removed", "none", "infers threat from stationary people; will not be built", "rejected"),
    ("cctv_coverage", "-", "removed", "institutional", "not proposed", "rejected"),
    ("police_crime_records", "-", "removed", "institutional", "not proposed", "rejected"),
    ("osm_lit_tag", "OSM lit=yes as current illumination", "removed", "none", "records installation, not tonight's state", "rejected"),
]


def check_catalog(con):
    bad = con.execute("SELECT field FROM collection_catalog WHERE permission_class='institutional' AND dependency_status!='rejected'").fetchall()
    assert not bad, f"institutional dependency in v1: {[r[0] for r in bad]}"
