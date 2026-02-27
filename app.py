from __future__ import annotations

import math
import os
import uuid
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

# IMPORTANT: set_page_config must be the first Streamlit call
st.set_page_config(page_title="Line Shop + CLV Tracker", page_icon="📉", layout="wide")

# =========================
# Paths (optional sample CSVs)
# =========================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(APP_DIR, "samples")
SAMPLE_OFFERS_PATH = os.path.join(SAMPLES_DIR, "sample_offers.csv")
SAMPLE_BETS_PATH = os.path.join(SAMPLES_DIR, "sample_bets.csv")

# =========================
# Helpers
# =========================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, str) and x.strip() == "":
            return None
        return float(x)
    except Exception:
        return None


def clean_text(x) -> str:
    """
    Converts NaN/None/"nan"/"none" to "" and always returns a safe string.
    """
    if x is None:
        return ""
    try:
        if pd.isna(x):
            return ""
    except Exception:
        pass
    s = str(x).strip()
    if s.lower() in {"nan", "none", "null"}:
        return ""
    return s


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def american_to_decimal(american: int) -> float:
    if american == 0:
        raise ValueError("American odds cannot be 0.")
    if american > 0:
        return 1.0 + (american / 100.0)
    return 1.0 + (100.0 / abs(american))


def implied_prob_from_decimal(decimal_odds: float) -> float:
    if decimal_odds <= 1.0:
        raise ValueError("Decimal odds must be > 1.00")
    return 1.0 / decimal_odds


def parse_odds_to_decimal(raw) -> Optional[float]:
    """
    Accepts:
      - Decimal: 1.91, "1.91"
      - American: -110, "+150", "-105"
    Returns decimal odds float or None.
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)) and not pd.isna(raw):
        x = float(raw)
        if abs(x) >= 100:
            try:
                return float(american_to_decimal(int(x)))
            except Exception:
                return None
        return x if x > 1.0 else None

    s = str(raw).strip().replace(" ", "").replace(",", ".")
    if s == "" or s.lower() in {"nan", "none", "null"}:
        return None

    if s.startswith(("+", "-")):
        try:
            return float(american_to_decimal(int(float(s))))
        except Exception:
            return None

    try:
        x = float(s)
        if abs(x) >= 100:
            try:
                return float(american_to_decimal(int(x)))
            except Exception:
                return None
        return x if x > 1.0 else None
    except Exception:
        return None


def ev_per_1(dec_odds: Optional[float], fair_prob: Optional[float]) -> Optional[float]:
    """
    EV per $1 staked: EV = p*d - 1
    """
    d = safe_float(dec_odds)
    p = safe_float(fair_prob)
    if d is None or p is None:
        return None
    if d <= 1.0 or p < 0 or p > 1:
        return None
    return p * d - 1.0


def novig_probs(dec_a: float, dec_b: float) -> Optional[Tuple[float, float, float]]:
    """
    Returns (pA_no_vig, pB_no_vig, overround)
    """
    try:
        if dec_a <= 1.0 or dec_b <= 1.0:
            return None
        ia = 1.0 / dec_a
        ib = 1.0 / dec_b
        over = ia + ib
        if over <= 0:
            return None
        return (ia / over, ib / over, over)
    except Exception:
        return None


def clv_log(entry_dec: Optional[float], close_dec: Optional[float]) -> Optional[float]:
    if entry_dec is None or close_dec is None:
        return None
    if entry_dec <= 0 or close_dec <= 0:
        return None
    return math.log(entry_dec / close_dec)


def clv_implied(entry_dec: Optional[float], close_dec: Optional[float]) -> Optional[float]:
    if entry_dec is None or close_dec is None:
        return None
    try:
        return implied_prob_from_decimal(close_dec) - implied_prob_from_decimal(entry_dec)
    except Exception:
        return None


def spread_clv_points(entry_line: Optional[float], close_line: Optional[float]) -> Optional[float]:
    if entry_line is None or close_line is None:
        return None
    return entry_line - close_line


def total_clv_points(direction: str, entry_total: Optional[float], close_total: Optional[float]) -> Optional[float]:
    if entry_total is None or close_total is None:
        return None
    if direction == "Over":
        return close_total - entry_total
    if direction == "Under":
        return entry_total - close_total
    return None


# =========================
# Data model
# =========================
OFFERS_COLS = [
    "offer_id",
    "created_at",
    "sport",
    "league",
    "game",
    "market_type",
    "side",
    "line",
    "odds_decimal",
    "book",
    "fair_prob",
    "notes",
]

BETS_COLS = [
    "bet_id",
    "created_at",
    "sport",
    "league",
    "game",
    "market_type",
    "direction",
    "side",
    "entry_line",
    "entry_odds_decimal",
    "entry_book",
    "stake",
    "fair_prob",
    "notes",
    "close_line",
    "close_odds_decimal",
    "close_at",
    "result",
]


def ensure_state():
    if "offers_df" not in st.session_state:
        st.session_state.offers_df = pd.DataFrame(columns=OFFERS_COLS)
    if "bets_df" not in st.session_state:
        st.session_state.bets_df = pd.DataFrame(columns=BETS_COLS)

    if "selected_offer_id" not in st.session_state:
        st.session_state.selected_offer_id = ""
    if "selected_offer_snapshot" not in st.session_state:
        st.session_state.selected_offer_snapshot = {}

    defaults = {
        "offer_sport": "NFL",
        "offer_league": "NFL",
        "offer_game": "KC @ BUF",
        "offer_market_type": "ML",
        "offer_side": "BUF",
        "offer_line": "",
        "offer_book": "Book A",
        "offer_odds_raw": "1.91",
        "offer_fair_prob": "",
        "offer_notes": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


ensure_state()


# =========================
# Demo + CSV schema conversion
# =========================
def demo_offers_df() -> pd.DataFrame:
    rows = [
        {"offer_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "ML", "side": "BUF", "line": "", "odds_decimal": 1.91, "book": "Book A", "fair_prob": 0.55, "notes": "Example offer"},
        {"offer_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "ML", "side": "BUF", "line": "", "odds_decimal": 1.95, "book": "Book B", "fair_prob": 0.55, "notes": "Better price"},
        {"offer_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "Spread", "side": "BUF", "line": -2.5, "odds_decimal": 1.91, "book": "Book A", "fair_prob": "", "notes": ""},
        {"offer_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "Total", "side": "Over", "line": 47.5, "odds_decimal": 1.87, "book": "Book A", "fair_prob": "", "notes": ""},
        {"offer_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "Total", "side": "Over", "line": 47.5, "odds_decimal": 1.91, "book": "Book B", "fair_prob": "", "notes": "Better total price"},
    ]
    return pd.DataFrame(rows, columns=OFFERS_COLS)


def demo_bets_df() -> pd.DataFrame:
    rows = [
        {"bet_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "ML", "direction": "", "side": "BUF", "entry_line": "", "entry_odds_decimal": 1.95, "entry_book": "Book B",
         "stake": 25.0, "fair_prob": 0.55, "notes": "Demo bet", "close_line": "", "close_odds_decimal": 1.83, "close_at": now_str(), "result": ""},
        {"bet_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "Total", "direction": "Over", "side": "Over", "entry_line": 47.5, "entry_odds_decimal": 1.91, "entry_book": "Book B",
         "stake": 20.0, "fair_prob": 0.54, "notes": "", "close_line": 48.5, "close_odds_decimal": 1.87, "close_at": now_str(), "result": ""},
        {"bet_id": str(uuid.uuid4())[:8], "created_at": now_str(), "sport": "NFL", "league": "NFL", "game": "KC @ BUF",
         "market_type": "Spread", "direction": "", "side": "BUF", "entry_line": -2.5, "entry_odds_decimal": 1.91, "entry_book": "Book A",
         "stake": 20.0, "fair_prob": 0.53, "notes": "", "close_line": -3.5, "close_odds_decimal": 1.91, "close_at": now_str(), "result": ""},
    ]
    return pd.DataFrame(rows, columns=BETS_COLS)


def normalize_offers_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Already our schema?
    if "offer_id" in out.columns and "odds_decimal" in out.columns:
        for c in OFFERS_COLS:
            if c not in out.columns:
                out[c] = ""
        out = out[OFFERS_COLS].copy()
    else:
        # Convert from older/newer schemas (date/event/market/selection/odds/book/fair_prob/notes)
        def pick(*names, default=""):
            for n in names:
                if n in out.columns:
                    return out[n]
            return pd.Series([default] * len(out))

        date_s = pick("date", default=datetime.now().strftime("%Y-%m-%d")).astype(str)
        event_s = pick("event", "game", default="").astype(str)
        market_s = pick("market", "market_type", default="ML").astype(str)
        side_s = pick("selection", "side", default="").astype(str)
        line_s = pick("line", default="")
        odds_s = pick("odds", "odds_decimal", default="")
        book_s = pick("book", default="").astype(str)
        fair_s = pick("fair_prob", default="")
        notes_s = pick("notes", default="").astype(str)

        out = pd.DataFrame({
            "offer_id": [str(uuid.uuid4())[:8] for _ in range(len(out))],
            "created_at": [f"{d} 00:00:00" for d in date_s],
            "sport": "NFL",
            "league": "NFL",
            "game": event_s,
            "market_type": market_s,
            "side": side_s,
            "line": line_s,
            "odds_decimal": odds_s,
            "book": book_s,
            "fair_prob": fair_s,
            "notes": notes_s,
        })

    # Normalize numeric
    out["odds_decimal"] = out["odds_decimal"].apply(parse_odds_to_decimal)
    out["fair_prob"] = out["fair_prob"].apply(safe_float)
    out["line"] = out["line"].apply(lambda x: "" if (x is None or (isinstance(x, float) and pd.isna(x))) else x)
    out["offer_id"] = out["offer_id"].apply(lambda x: clean_text(x) or str(uuid.uuid4())[:8])

    # Clean text fields to avoid nan showing up anywhere
    for col in ["created_at", "sport", "league", "game", "market_type", "side", "book", "notes"]:
        out[col] = out[col].apply(clean_text)

    return out


def normalize_bets_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if "bet_id" in out.columns and "entry_odds_decimal" in out.columns:
        for c in BETS_COLS:
            if c not in out.columns:
                out[c] = ""
        out = out[BETS_COLS].copy()
    else:
        def pick(*names, default=""):
            for n in names:
                if n in out.columns:
                    return out[n]
            return pd.Series([default] * len(out))

        date_s = pick("date", default=datetime.now().strftime("%Y-%m-%d")).astype(str)
        event_s = pick("event", "game", default="").astype(str)
        market_s = pick("market", "market_type", default="ML").astype(str)
        side_s = pick("selection", "side", default="").astype(str)
        entry_line_s = pick("entry_line", default="")
        entry_odds_s = pick("entry_odds", "entry_odds_decimal", default="")
        entry_book_s = pick("entry_book", default="").astype(str)
        stake_s = pick("stake", default="")
        close_line_s = pick("close_line", default="")
        close_odds_s = pick("close_odds", "close_odds_decimal", default="")
        notes_s = pick("notes", default="").astype(str)
        fair_s = pick("fair_prob", default="")

        direction = []
        for m, s in zip(market_s.astype(str), side_s.astype(str)):
            if str(m).strip().lower() == "total" and s.strip().lower() in {"over", "under"}:
                direction.append(s.strip().title())
            else:
                direction.append("")

        out = pd.DataFrame({
            "bet_id": [str(uuid.uuid4())[:8] for _ in range(len(out))],
            "created_at": [f"{d} 00:00:00" for d in date_s],
            "sport": "NFL",
            "league": "NFL",
            "game": event_s,
            "market_type": market_s,
            "direction": direction,
            "side": side_s,
            "entry_line": entry_line_s,
            "entry_odds_decimal": entry_odds_s,
            "entry_book": entry_book_s,
            "stake": stake_s,
            "fair_prob": fair_s,
            "notes": notes_s,
            "close_line": close_line_s,
            "close_odds_decimal": close_odds_s,
            "close_at": "",
            "result": "",
        })

    out["entry_odds_decimal"] = out["entry_odds_decimal"].apply(parse_odds_to_decimal)
    out["close_odds_decimal"] = out["close_odds_decimal"].apply(parse_odds_to_decimal)
    out["stake"] = out["stake"].apply(safe_float)
    out["fair_prob"] = out["fair_prob"].apply(safe_float)
    out["bet_id"] = out["bet_id"].apply(lambda x: clean_text(x) or str(uuid.uuid4())[:8])

    for col in ["created_at", "sport", "league", "game", "market_type", "direction", "side", "entry_book", "notes", "close_at", "result"]:
        out[col] = out[col].apply(clean_text)

    return out


def try_read_csv(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


def load_demo():
    offers_raw = try_read_csv(SAMPLE_OFFERS_PATH)
    bets_raw = try_read_csv(SAMPLE_BETS_PATH)

    offers = normalize_offers_df(offers_raw) if offers_raw is not None else normalize_offers_df(demo_offers_df())
    bets = normalize_bets_df(bets_raw) if bets_raw is not None else normalize_bets_df(demo_bets_df())

    st.session_state.offers_df = offers
    st.session_state.bets_df = bets
    st.session_state.selected_offer_id = ""
    st.session_state.selected_offer_snapshot = {}
    st.toast("Demo loaded ✅", icon="✅")
    st.rerun()


def clear_all():
    st.session_state.offers_df = pd.DataFrame(columns=OFFERS_COLS)
    st.session_state.bets_df = pd.DataFrame(columns=BETS_COLS)
    st.session_state.selected_offer_id = ""
    st.session_state.selected_offer_snapshot = {}
    st.toast("Cleared ✅", icon="🧹")
    st.rerun()


def selectable_dataframe(df: pd.DataFrame, key: str) -> Optional[int]:
    if df is None or df.empty:
        st.dataframe(df, use_container_width=True, hide_index=True)
        return None

    try:
        event = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key=key,
            height="auto",
        )
        rows = []
        try:
            rows = list(event.selection.rows)
        except Exception:
            try:
                rows = list(event["selection"]["rows"])
            except Exception:
                rows = []
        return rows[0] if rows else None
    except TypeError:
        st.dataframe(df, use_container_width=True, hide_index=True)
        idx = st.selectbox(
            "Pick a row",
            list(range(len(df))),
            format_func=lambda i: f"Row {i+1}",
            key=f"{key}_fallback",
        )
        return int(idx) if idx is not None else None


def copy_selected_into_offer_form():
    sel = st.session_state.get("selected_offer_snapshot", {}) or {}
    if not sel:
        st.toast("Select a row first.", icon="⚠️")
        return

    st.session_state["offer_sport"] = clean_text(sel.get("sport", "NFL"))
    st.session_state["offer_league"] = clean_text(sel.get("league", "NFL"))
    st.session_state["offer_game"] = clean_text(sel.get("game", ""))
    st.session_state["offer_market_type"] = clean_text(sel.get("market_type", "ML"))
    st.session_state["offer_side"] = clean_text(sel.get("side", ""))
    st.session_state["offer_line"] = clean_text(sel.get("line", ""))
    st.session_state["offer_book"] = clean_text(sel.get("book", ""))
    st.session_state["offer_notes"] = clean_text(sel.get("notes", ""))
    fp = sel.get("fair_prob", "")
    st.session_state["offer_fair_prob"] = "" if fp is None else clean_text(fp)
    od = sel.get("odds_decimal", "")
    st.session_state["offer_odds_raw"] = "" if od is None else clean_text(od)

    st.toast("Copied into Add Offer form ✅", icon="✅")


# =========================
# UI
# =========================
st.title("Line Shop + CLV Tracker")
st.caption("Workflow: log offers → pick best price → create bet → add close → track CLV")

with st.sidebar:
    st.header("Controls")
    c1, c2 = st.columns(2)

    if c1.button("Load demo", use_container_width=True):
        load_demo()
    if c2.button("Clear all", use_container_width=True):
        clear_all()

    st.caption(f"Offers: **{len(st.session_state.offers_df)}**  •  Bets: **{len(st.session_state.bets_df)}**")
    st.caption("Tip: click a row in **Best prices** → copy into form or create a bet.")

tabs = st.tabs(["Line Shop", "CLV Tracker", "Import / Export", "About"])


# =========================
# TAB 1: LINE SHOP
# =========================
with tabs[0]:
    st.subheader("Line Shop")

    with st.expander("Add an offer (book line)", expanded=True):
        with st.form("add_offer_form", clear_on_submit=False):
            a1, a2, a3, a4 = st.columns([1, 1, 2, 1])
            sport = a1.text_input("Sport", key="offer_sport")
            league = a2.text_input("League", key="offer_league")
            game = a3.text_input("Game (e.g., KC @ BUF)", key="offer_game")
            market_type = a4.selectbox("Market type", ["ML", "Spread", "Total"], key="offer_market_type")

            b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
            side = b1.text_input("Side", key="offer_side", help="Examples: BUF / KC / Over / Under")
            line = b2.text_input("Line (optional)", key="offer_line", help="Spread/Total numeric. Examples: -2.5, 47.5")
            book = b3.text_input("Book", key="offer_book")
            fair_prob_raw = b4.text_input("Fair prob (optional 0–1)", key="offer_fair_prob")

            o1, o2 = st.columns([1, 2])
            odds_raw = o2.text_input("Odds (paste 1.95 or -110 or +150)", key="offer_odds_raw")
            dec = parse_odds_to_decimal(odds_raw)
            if dec is None:
                o1.error("Odds not valid")
            else:
                o1.markdown(f"Decimal: **{dec:.3f}**")

            notes = st.text_input("Notes (optional)", key="offer_notes")

            submitted = st.form_submit_button("Add offer to list", use_container_width=True)
            if submitted:
                try:
                    if dec is None or float(dec) <= 1.0:
                        raise ValueError("Odds must parse to decimal > 1.00")
                    fp = safe_float(fair_prob_raw) if clean_text(fair_prob_raw) else None
                    if fp is not None and (fp < 0 or fp > 1):
                        raise ValueError("Fair prob must be between 0 and 1.")
                    line_f = safe_float(line)

                    new_row = {
                        "offer_id": str(uuid.uuid4())[:8],
                        "created_at": now_str(),
                        "sport": clean_text(sport),
                        "league": clean_text(league),
                        "game": clean_text(game),
                        "market_type": clean_text(market_type),
                        "side": clean_text(side),
                        "line": "" if line_f is None else line_f,
                        "odds_decimal": round(float(dec), 4),
                        "book": clean_text(book),
                        "fair_prob": "" if fp is None else float(fp),
                        "notes": clean_text(notes),
                    }
                    st.session_state.offers_df = pd.concat(
                        [st.session_state.offers_df, pd.DataFrame([new_row])],
                        ignore_index=True,
                    )
                    st.toast("Offer added ✅", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add offer: {e}")

    offers_df = normalize_offers_df(st.session_state.offers_df.copy())
    st.session_state.offers_df = offers_df

    if offers_df.empty:
        st.info("Add offers above, or click **Load demo** in the sidebar.")
    else:
        view = offers_df.copy()
        view["odds_decimal"] = pd.to_numeric(view["odds_decimal"], errors="coerce")
        view["line_num"] = pd.to_numeric(view["line"], errors="coerce")
        view["fair_prob_num"] = pd.to_numeric(view["fair_prob"], errors="coerce")

        key_cols = ["sport", "league", "game", "market_type", "side", "line"]
        best = (
            view.dropna(subset=["odds_decimal"])
            .groupby(key_cols, dropna=False)["odds_decimal"]
            .max()
            .reset_index()
            .rename(columns={"odds_decimal": "best_odds"})
        )

        merged = view.merge(best, on=key_cols, how="left")
        merged["is_best"] = merged["odds_decimal"] == merged["best_odds"]
        merged["implied_prob"] = merged["odds_decimal"].apply(
            lambda o: (1.0 / float(o)) if pd.notna(o) and float(o) > 0 else None
        )
        merged["ev_per_$1"] = merged.apply(lambda r: ev_per_1(r.get("odds_decimal"), r.get("fair_prob_num")), axis=1)

        st.markdown("### Offers")
        st.dataframe(
            merged.fillna(""),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("### Best prices (click a row to select it)")
        best_only = merged[merged["is_best"]].copy().fillna("")
        best_only = best_only.sort_values(
            ["game", "market_type", "side", "line_num"], ascending=[True, True, True, True]
        ).reset_index(drop=True)

        best_only.insert(0, "best_flag", "✅")
        best_table = best_only[
            ["offer_id", "best_flag", "sport", "league", "game", "market_type", "side", "line", "odds_decimal", "book", "fair_prob", "implied_prob", "ev_per_$1", "notes"]
        ].copy()

        selected_pos = selectable_dataframe(best_table, key="best_prices_table")
        if selected_pos is not None:
            st.session_state.selected_offer_id = str(best_table.iloc[int(selected_pos)]["offer_id"])

        selected_offer = None
        if st.session_state.selected_offer_id:
            match = merged[merged["offer_id"].astype(str) == str(st.session_state.selected_offer_id)]
            if not match.empty:
                selected_offer = match.iloc[0].to_dict()
                st.session_state.selected_offer_snapshot = selected_offer

        if selected_offer:
            st.markdown("### Selected offer")
            st.write(
                f"**{selected_offer.get('game')}** • {selected_offer.get('market_type')} • {selected_offer.get('side')} "
                f"• line: `{selected_offer.get('line')}` • odds: **{selected_offer.get('odds_decimal')}** • book: {selected_offer.get('book')}"
            )

            c1, c2 = st.columns([1, 1])
            c1.button(
                "Copy selected into Add Offer form",
                on_click=copy_selected_into_offer_form,
                use_container_width=True,
            )

            if c2.button("Create bet from selected offer", use_container_width=True):
                sel_odds = safe_float(selected_offer.get("odds_decimal"))
                market_type = clean_text(selected_offer.get("market_type", ""))
                side = clean_text(selected_offer.get("side", ""))
                direction = side if (market_type == "Total" and side.lower() in {"over", "under"}) else ""

                new_bet = {
                    "bet_id": str(uuid.uuid4())[:8],
                    "created_at": now_str(),
                    "sport": clean_text(selected_offer.get("sport", "")),
                    "league": clean_text(selected_offer.get("league", "")),
                    "game": clean_text(selected_offer.get("game", "")),
                    "market_type": market_type,
                    "direction": direction,
                    "side": side,
                    "entry_line": clean_text(selected_offer.get("line", "")),
                    "entry_odds_decimal": "" if sel_odds is None else round(float(sel_odds), 4),
                    "entry_book": clean_text(selected_offer.get("book", "")),
                    "stake": 25.0,
                    "fair_prob": selected_offer.get("fair_prob", ""),
                    "notes": "",
                    "close_line": "",
                    "close_odds_decimal": "",
                    "close_at": "",
                    "result": "",
                }
                st.session_state.bets_df = pd.concat(
                    [st.session_state.bets_df, pd.DataFrame([new_bet])],
                    ignore_index=True,
                )
                st.toast("Bet created ✅ (go to CLV Tracker)", icon="✅")
                st.rerun()

        with st.expander("Fair probability helper (implied + no-vig)"):
            st.caption("Market-based estimates: implied prob from one side, or no-vig from both sides.")
            h1, h2, h3 = st.columns(3)

            odds_one = h1.text_input("Single odds → implied prob", value="1.95")
            dec_one = parse_odds_to_decimal(odds_one)
            if dec_one:
                h1.markdown(f"Implied p = **{(1/dec_one):.4f}** ({pct(1/dec_one)})")

            odds_a = h2.text_input("Side A odds", value="1.95")
            odds_b = h3.text_input("Side B odds", value="1.91")
            dec_a = parse_odds_to_decimal(odds_a)
            dec_b = parse_odds_to_decimal(odds_b)
            if dec_a and dec_b:
                res = novig_probs(float(dec_a), float(dec_b))
                if res:
                    pA, pB, over = res
                    st.markdown(
                        f"**No-vig fair probs**:\n\n"
                        f"- Side A: **{pA:.4f}** ({pct(pA)})\n"
                        f"- Side B: **{pB:.4f}** ({pct(pB)})\n"
                        f"- Overround: **{over:.4f}** (vig ≈ {(over-1)*100:.2f}%)"
                    )


# =========================
# TAB 2: CLV TRACKER
# =========================
with tabs[1]:
    st.subheader("CLV Tracker")

    bets_df = normalize_bets_df(st.session_state.bets_df.copy())
    st.session_state.bets_df = bets_df

    if bets_df.empty:
        st.info("Create a bet from Line Shop, or click **Load demo** in the sidebar.")
    else:
        st.markdown("### Update closing line / odds")
        pick = st.selectbox("Select bet_id", bets_df["bet_id"].tolist())
        row = bets_df[bets_df["bet_id"] == pick].iloc[0].to_dict()
        st.caption(f"{row.get('game')} • {row.get('market_type')} • {row.get('side')}")

        u1, u2, u3 = st.columns([1, 1, 1])
        close_line = u1.text_input("Closing line (optional)", value=str(row.get("close_line", "")))
        close_odds_raw = u2.text_input("Closing odds (paste 1.83 or -120, optional)", value=str(row.get("close_odds_decimal", "")))
        result = u3.selectbox("Result", ["", "Win", "Loss", "Push"], index=0)

        close_at = st.text_input("Close timestamp (optional)", value=now_str())

        if st.button("Save closing update", use_container_width=True):
            close_line_f = safe_float(close_line)
            close_dec_f = parse_odds_to_decimal(close_odds_raw) if clean_text(close_odds_raw) else None

            idx = bets_df.index[bets_df["bet_id"] == pick][0]
            bets_df.loc[idx, "close_line"] = "" if close_line_f is None else close_line_f
            bets_df.loc[idx, "close_odds_decimal"] = "" if close_dec_f is None else round(float(close_dec_f), 4)
            bets_df.loc[idx, "close_at"] = clean_text(close_at)
            bets_df.loc[idx, "result"] = clean_text(result)
            st.session_state.bets_df = bets_df
            st.toast("Updated ✅", icon="✅")
            st.rerun()

        st.divider()

        view = bets_df.copy()
        view["entry_odds_decimal"] = pd.to_numeric(view["entry_odds_decimal"], errors="coerce")
        view["close_odds_decimal"] = pd.to_numeric(view["close_odds_decimal"], errors="coerce")
        view["entry_line_num"] = pd.to_numeric(view["entry_line"], errors="coerce")
        view["close_line_num"] = pd.to_numeric(view["close_line"], errors="coerce")

        view["clv_log"] = [clv_log(e, c) for e, c in zip(view["entry_odds_decimal"], view["close_odds_decimal"])]
        view["clv_implied"] = [clv_implied(e, c) for e, c in zip(view["entry_odds_decimal"], view["close_odds_decimal"])]

        view["spread_clv_pts"] = view.apply(
            lambda r: spread_clv_points(r["entry_line_num"], r["close_line_num"]) if r["market_type"] == "Spread" else None,
            axis=1,
        )
        view["total_clv_pts"] = view.apply(
            lambda r: total_clv_points(str(r.get("direction", "")), r["entry_line_num"], r["close_line_num"]) if r["market_type"] == "Total" else None,
            axis=1,
        )

        has_close = view["clv_log"].notna()
        n_close = int(has_close.sum())
        pos = int((view.loc[has_close, "clv_log"] > 0).sum()) if n_close else 0
        avg_clv = float(view.loc[has_close, "clv_log"].mean()) if n_close else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Bets logged", str(len(view)))
        m2.metric("With close odds", str(n_close))
        m3.metric("% Positive CLV (log)", pct(pos / n_close) if n_close else "—")
        m4.metric("Avg CLV (log)", f"{avg_clv:+.4f}")

        st.dataframe(view.fillna(""), use_container_width=True, hide_index=True)


# =========================
# TAB 3: Import / Export
# =========================
with tabs[2]:
    st.subheader("Import / Export")

    c1, c2 = st.columns(2)
    c1.download_button("Download offers.csv", data=df_to_csv_bytes(st.session_state.offers_df), file_name="offers_export.csv", mime="text/csv", use_container_width=True)
    c2.download_button("Download bets.csv", data=df_to_csv_bytes(st.session_state.bets_df), file_name="bets_export.csv", mime="text/csv", use_container_width=True)


# =========================
# TAB 4: About
# =========================
with tabs[3]:
    st.subheader("About")
    st.markdown(
        """
This app is a workflow tool:

- **Line shopping:** log offers across books → pick best prices.
- **Bet logging:** create bets from selected offers.
- **CLV tracking:** compare entry odds/line to the close.

**Fair probability**
- You can enter your own model probability, or
- Use the helper to estimate market no-vig probabilities.
"""
    )