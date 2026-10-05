import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from download import unpack  # noqa: E402


def test_unpack_preserves_ixbrl_schema_and_linkbase_filenames(tmp_path):
    submission = tmp_path / "full-submission.txt"
    submission.write_text(
        """<DOCUMENT>
<FILENAME>akam-20241231.htm
<TEXT><html><body>Inline XBRL</body></html></TEXT>
</DOCUMENT>
<DOCUMENT>
<FILENAME>akam-20241231.xsd
<TEXT><XBRL><schema>schema content</schema></XBRL></TEXT>
</DOCUMENT>
<DOCUMENT>
<FILENAME>akam-20241231_cal.xml
<TEXT><XML><linkbase>calculation linkbase</linkbase></XML></TEXT>
</DOCUMENT>
<DOCUMENT>
<FILENAME>readme.txt
<TEXT>not an XBRL resource</TEXT>
</DOCUMENT>
""",
        encoding="utf-8",
    )

    out = unpack(submission)

    assert out == tmp_path / "unpacked"
    assert (out / "akam-20241231.htm").read_text() == "<html><body>Inline XBRL</body></html>"
    assert (out / "akam-20241231.xsd").read_text() == "<schema>schema content</schema>"
    assert (out / "akam-20241231_cal.xml").read_text() == "<linkbase>calculation linkbase</linkbase>"
    assert sorted(path.name for path in out.iterdir()) == [
        "akam-20241231.htm",
        "akam-20241231.xsd",
        "akam-20241231_cal.xml",
    ]
