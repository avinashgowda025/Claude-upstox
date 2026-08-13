"""CSS for the mobile-friendly, premium-feeling dashboard shell."""
import streamlit as st

CSS = """
<style>
:root { --card-radius: 16px; }
.block-container {
  max-width: 1450px;
  padding-top: 1.15rem;
  padding-bottom: 3rem;
}
[data-testid="stSidebar"] { min-width: 270px; max-width: 270px; }
[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
.hero-card {
  border: 1px solid rgba(255,255,255,.12);
  border-radius: 18px;
  padding: 22px 24px;
  margin: 6px 0 14px 0;
  background: linear-gradient(135deg, rgba(255,255,255,.075), rgba(255,255,255,.025));
}
.hero-title { font-size: 2rem; font-weight: 750; letter-spacing: -.02em; margin-bottom: 4px; }
.hero-sub { opacity: .72; font-size: .92rem; }
.signal-pill {
  display: inline-block;
  padding: 7px 12px;
  border-radius: 999px;
  font-weight: 700;
  font-size: .84rem;
  margin-bottom: 10px;
  border: 1px solid rgba(255,255,255,.14);
}
.signal-green { background: rgba(34,197,94,.14); }
.signal-red { background: rgba(239,68,68,.14); }
.signal-blue { background: rgba(59,130,246,.14); }
.signal-yellow { background: rgba(234,179,8,.14); }
.status-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .03em;
  border: 1px solid rgba(255,255,255,.14);
  margin-left: 8px;
  vertical-align: middle;
}
.status-open { background: rgba(34,197,94,.14); }
.status-closed { background: rgba(148,163,184,.16); }
.level-card {
  border: 1px solid rgba(255,255,255,.09);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(255,255,255,.035);
}
.section-kicker {
  text-transform: uppercase;
  letter-spacing: .08em;
  font-size: .72rem;
  font-weight: 700;
  opacity: .55;
  margin-bottom: 3px;
}
.learning-note {
  border-left: 3px solid rgba(96,165,250,.75);
  padding: 9px 13px;
  background: rgba(96,165,250,.06);
  border-radius: 0 10px 10px 0;
}
div[data-testid="stMetric"] {
  border: 1px solid rgba(255,255,255,.07);
  border-radius: 12px;
  padding: 10px 12px;
  background: rgba(255,255,255,.025);
}
@media (max-width: 800px) {
  .block-container { padding-left: .8rem; padding-right: .8rem; }
  [data-testid="stSidebar"] { min-width: 260px; max-width: 260px; }
  .hero-title { font-size: 1.55rem; }
}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
