import os
import requests
import streamlit as st

API_DEFAULT = os.getenv("API_BASE_URL", "http://localhost:8000")
st.set_page_config(page_title="ISO Middleware Admin", layout="centered")

st.title("ISO 20022 Middleware Admin Panel")

with st.sidebar:
    api_base = st.text_input("API Base URL", value=API_DEFAULT, help="e.g. http://localhost:8000")

tab1, tab2 = st.tabs(["Receipts", "Verify Bundle"])

with tab1:
    st.subheader("Fetch Receipt")
    rid = st.text_input("Receipt ID (UUID)")
    if st.button("Fetch Receipt", type="primary"):
        try:
            r = requests.get(f"{api_base}/v1/iso/receipts/{rid}", timeout=20)
            if r.status_code == 200:
                data = r.json()
                st.success(f"Status: {data.get('status')}")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("Receipt")
                    st.json({
                        "id": data.get("id"),
                        "bundle_hash": data.get("bundle_hash"),
                        "flare_txid": data.get("flare_txid"),
                        "created_at": data.get("created_at"),
                        "anchored_at": data.get("anchored_at"),
                    })
                with col2:
                    st.write("Artifacts")
                    xml_url = data.get("xml_url")
                    bundle_url = data.get("bundle_url")
                    if xml_url:
                        st.markdown(f"[pain001.xml]({api_base}{xml_url})")
                    if bundle_url:
                        st.markdown(f"[evidence.zip]({api_base}{bundle_url})")
                    if data.get("flare_txid"):
                        st.markdown(f"Flare tx: `{data.get('flare_txid')}`")

                st.divider()
                st.write("Zero‑polling options")
                receipt_url = f"{api_base}/receipt/{data.get('id')}"
                st.markdown(f"[Open live receipt page]({receipt_url})")

                try:
                    import streamlit.components.v1 as components  # lazy import
                    embed_url = f"{api_base}/embed/receipt?rid={data.get('id')}"
                    components.iframe(embed_url, height=160)
                except Exception:
                    st.info("Embed requires components; falling back to link above.")
            else:
                try:
                    st.error(f"{r.status_code}: {r.json().get('detail')}")
                except Exception:
                    st.error(f"HTTP {r.status_code}")
        except Exception as e:
            st.error(f"Request failed: {e}")

with tab2:
    st.subheader("Verify Evidence Bundle")
    bundle_url = st.text_input("Bundle URL (e.g., http://localhost:8000/files/<id>/evidence.zip)")
    if st.button("Verify Bundle", type="primary"):
        try:
            r = requests.post(f"{api_base}/v1/iso/verify", json={"bundle_url": bundle_url}, timeout=60)
            if r.status_code == 200:
                data = r.json()
                if data.get("matches_onchain"):
                    st.success("On-chain evidence matches bundle hash.")
                else:
                    st.warning("No on-chain match found for this bundle hash.")
                st.json(data)
            else:
                try:
                    st.error(f"{r.status_code}: {r.json().get('detail')}")
                except Exception:
                    st.error(f"HTTP {r.status_code}")
        except Exception as e:
            st.error(f"Verification failed: {e}")

st.caption("Set API_BASE_URL env or use the sidebar to point to your API.")
