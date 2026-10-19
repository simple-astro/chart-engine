"""Front-end fixes from the QA pass, checked on the shipped index.html: routing, Match making, the timezone field,
the chat limit and the "Go deeper" chips. Pure helpers run under node when it is installed."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

INDEX = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text()


def _between(text, start, end):
    i = text.index(start)
    return text[i:text.index(end, i)]


# ----- P1 navigation -----
def test_match_making_lives_with_the_bottom_bar_and_has_a_way_out():
    out = _between(INDEX, '<section id="out"', '<div class="scr" id="s-today"')
    assert 'id="sjbar"' in out and '<section id="viewMatch"' in out  # same area, so the bar shows on Match
    assert 'id="mback"' in _between(INDEX, '<section id="viewMatch"', "</section>")
    assert re.search(r'<a class="brand" id="brand" href="#today"', INDEX)  # the logo goes to Today


def test_one_router_for_every_view():
    script = INDEX[INDEX.index("// ----- routing:"):]
    assert "function route(){" in script and "function nav(hash,o){" in script
    route = _between(script, "function route(){", "\n}\n")
    for h in ("'new'", "'edit'", "'match'"):
        assert h in route
    assert "go('today',undefined,{replace:true})" in route  # unknown routes fall back to Today
    assert "addEventListener('hashchange',onHash)" in INDEX and "addEventListener('popstate',onHash)" in INDEX
    assert "$('matchbtn').onclick=()=>{closeMenu();nav('match')}" in INDEX
    assert "nav('new')" in _between(INDEX, "$('newbtn').onclick=", "\n")
    # nav() always routes, so a tap on the item you are on still works; go() records screens in history
    assert re.search(r"function nav\(hash,o\)\{[^}]*\n[^\n]*\n\s*route\(\);", INDEX)
    assert "pushState'" in _between(INDEX, "function go(name,sub,o){", "\nfunction loadVisible")
    # the old handler that ignored hashes while another view was showing is gone
    assert "if(!$('out').hidden){const[h,sub]=location.hash" not in INDEX


# ----- P2 timezone -----
def test_timezone_field_shows_its_own_error():
    assert 'aria-describedby="tzerr"' in INDEX and 'id="tzerr"' in INDEX and 'list="tzlist"' in INDEX
    submit = _between(INDEX, "$('f').addEventListener('submit'", "\n});")
    assert "validTz(body.tz_name)" in submit and "d.field==='tz'" in submit
    assert "'Error: '+err.message" not in submit
    assert "Intl.supportedValuesOf('timeZone')" in INDEX


# ----- P4 -----
def test_match_needs_two_different_profiles():
    assert 'id="madd"' in INDEX and "Add a second profile" in INDEX
    ready = _between(INDEX, "function matchReady(){", "\n")
    assert "profiles.length>=2&&$('mgroom').value!==$('mbride').value" in ready


def test_chat_switches_off_at_the_daily_limit():
    paint = _between(INDEX, "function paintLimit(){", "\n}\n")
    assert "$('q').disabled=!on" in paint and "Daily limit reached" in paint and "resets_at" in paint
    submit = _between(INDEX, "$('askf').addEventListener('submit'", "\n});")
    assert "paintLimit()" in submit and "$('askbtn').disabled=false" not in submit


def test_ayanamsha_is_remembered_and_place_search_is_debounced():
    assert "localStorage.setItem('sj-ayanamsha'" in INDEX and "lastAyan()" in INDEX
    assert "SEARCH_T=setTimeout(search," in INDEX and "AbortController" in INDEX and 'class="spin"' in INDEX


def test_unknown_birth_time_softens_the_lagna():
    assert "needs birth time" in INDEX and "noTime" in INDEX


# ----- pure helpers, run for real -----
NODE = shutil.which("node")


def _js(expr: str):
    helpers = INDEX[INDEX.index("window.apiErr="):INDEX.index("\n", INDEX.index("window.apiErr="))] + "\n"
    helpers += _between(INDEX, "const DEEPER=", "function deeper(q,answer){")
    code = "const window={};const esc=s=>s;\n" + helpers.replace("window.apiErr=", "window.apiErr=") + \
        "\nconst apiErr=window.apiErr;\nconsole.log(JSON.stringify(" + expr + "))"
    return json.loads(subprocess.run([NODE, "-e", code], capture_output=True, text=True, check=True).stdout)



def test_my_charts_tab_has_the_sudarshan_chakra():
    bar = _between(INDEX, '<nav class="sjbar"', "</nav>")
    tab = _between(bar, '<button type="button" data-go="chart">', "</button>")
    assert "<title>Sudarshan Chakra</title>" in tab and "<span>My Charts</span>" in tab
    assert "chart:'My Charts'" in INDEX and ">Charts</button>" not in INDEX


def test_kp_branch_and_paryaya_in_transits():
    assert "nadi:'KP'" in _between(INDEX, "const BRANCHES=", "\n") and "Nadi (KP)" not in INDEX
    assert 'id="gparyaya"' in _between(INDEX, '<div id="tm-transits"', '<div id="tm-matter"')
    assert "if(SCREEN==='timing'&&TM==='transits')loadParyaya();" in INDEX


def test_nadi_amsha_is_the_d150_divisional_chart():
    assert 'id="t-nadi"' not in INDEX and 'data-pane="nadi"' not in INDEX and "nadiRow" not in INDEX
    assert "D150:'Nadi amsha" in INDEX and 'id="vnadi"' in _between(INDEX, 'id="t-vargas"', 'id="t-akv"')
    assert "nadiAmsha(c,k==='D150')" in INDEX and "Chandra Kala Nadi" in INDEX
    assert "if(name==='chart'&&sub==='d150'){sub='vargas';VWANT='D150'}" in INDEX


def test_kp_dasha_lords_table_sits_with_kp_timing():
    matter = _between(INDEX, '<div id="tm-matter"', '<div id="tm-dates"')
    assert matter.index('id="t-kpsig"') < matter.index('id="t-kptime"')
    assert "kpSigTable(c);" in INDEX and "['Planet','Star lord','Sub lord']" in INDEX


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_api_errors_read_as_one_line():
    assert _js("apiErr('Profile not found')") == "Profile not found"
    assert _js("apiErr({field:'tz',message:'We don’t recognise that timezone.'})") == "We don’t recognise that timezone."
    assert _js("apiErr([{msg:'a'},{msg:'b'}])") == "a; b"
    assert _js("apiErr(undefined)") == ""


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_go_deeper_follows_the_matter_discussed():
    marriage = _js("deeperPicks('When will I get married?','Your 7th house…')")
    assert len(marriage) == 3 and all("marriage" in p or "career" in p for p in marriage)
    assert not any(p.startswith("When") for p in marriage)  # timing was just asked
    career = _js("deeperPicks('Will I get a promotion?','')")
    assert any("my career" in p for p in career) and career != marriage
    remedy = _js("deeperPicks('What remedy helps my health?','')")
    assert not any("upaya" in p for p in remedy)  # a remedy was just asked


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_no_go_deeper_after_a_refusal():
    from app import chat
    src = Path(chat.__file__).read_text()
    refusal = re.search(r'"(I can\'t help with that question\. )"\s*\n\s*"(Please ask me something else[^"]*)"', src)
    assert refusal, "the server's refusal text moved: update REFUSED in index.html"
    text = refusal.group(1) + refusal.group(2)
    assert _js(f"REFUSED.test({json.dumps(text)})") is True
    assert _js("REFUSED.test('Your career looks steady this year.')") is False


def test_bnn_is_its_own_studies_branch():
    assert '<button type="button" role="listitem" data-branch="bnn">' in INDEX
    assert "bnn:'BNN'" in _between(INDEX, "const BRANCHES=", "\n") and "bnn:'bnn'" in INDEX
    assert 'data-pane="bnn" data-branch="bnn"' in INDEX
    nadi = _between(INDEX, 'data-branch="nadi"><i', "</button>")
    assert "BNN" not in nadi


def test_bnn_chart_shows_retrograde_planets_in_the_sign_before_too():
    draw = _between(INDEX, "  const drawMain=()=>{", "\n  };\n")
    assert "BRANCH==='bnn'" in draw and "(g.sign_index+11)%12" in draw and "n==='Rahu'||n==='Ketu'" in draw
    assert INDEX.count("p.ghost?'<tspan class=\"bnng\">") == 2  # North and South Indian charts
    assert "wasBnn!==(BRANCH==='bnn')" in _between(INDEX, "function setBranch(b){", "\n}\n")  # redrawn on switch


def test_yogini_dasha_sits_with_vimshottari_not_jaimini():
    now = _between(INDEX, '<div id="tm-now">', '<div id="tm-transits"')
    assert now.index('id="t-vim"') < now.index('id="t-yogini"') and 'id="yoginibody"' in now
    jai = _between(INDEX, '<div class="stx" data-for="jaimini"', '<div class="stx" data-for="lal"')
    assert "yogini" not in jai.lower() and 'id="yogbody"' in jai
    assert "'Yogini Dasha'," in INDEX and "'timing/yogini']" in INDEX


def test_prashna_is_a_main_tab():
    assert "const SCREENS=['today','timing','prashna','ask','remedies','chart'];" in INDEX
    assert '<button type="button" data-go="prashna">' in _between(INDEX, '<nav class="sjbar"', "</nav>")
    assert 'id="gprashna"' in _between(INDEX, '<div class="scr" id="s-prashna"', "</div>\n")
    assert 'data-branch="prashna"' not in INDEX and "prashna:'Prashna'};" not in INDEX  # gone from Charts
    assert "['prashna','kpq','jamakkol'].includes(sub)" in INDEX  # old #chart/prashna links still open it


def test_accuracy_nudge_is_off_for_now():
    assert "const ACC_NUDGE=false;" in INDEX and "if(ACC_NUDGE&&ACC.next" in INDEX


def test_tajika_is_a_charts_branch():
    assert '<button type="button" role="listitem" data-branch="tajika">' in INDEX
    assert "tajika:'Tajika'" in _between(INDEX, "const BRANCHES=", "\n")
    assert 'data-pane="tajika" data-branch="tajika"' in INDEX and 'id="t-tajika"' in INDEX
    assert "if(SCREEN==='chart'&&BRANCH==='tajika')loadTajika();" in INDEX


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_every_inline_script_parses(tmp_path):
    """A syntax error anywhere in the page's own scripts stops the whole app, so parse each one."""
    for i, js in enumerate(re.findall(r"<script>(.*?)</script>", INDEX, re.S)):
        f = tmp_path / f"inline{i}.js"
        f.write_text(js)
        r = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[:400]
    for name in ("tools.js", "transit.js", "guide.js", "events.js", "kptiming.js", "mood.js", "upcoming.js"):
        r = subprocess.run([NODE, "--check", str(Path(__file__).resolve().parent.parent / "app" / "static" / name)],
                           capture_output=True, text=True)
        assert r.returncode == 0, (name, r.stderr[:400])
