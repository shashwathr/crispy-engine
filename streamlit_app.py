import streamlit as st
import pandas as pd
import numpy as np


if "init" not in st.session_state:
    st.session_state.chart_data = pd.DataFrame(
        np.random.randn(20, 3), columns=["a", "b", "c"]
    )
    st.session_state.map_data = pd.DataFrame(
        np.random.randn(1000, 2) / [50, 50] + [37.76, -122.4],
        columns=["lat", "lon"],
    )
    st.session_state.init = True


pages = [
    st.Page(
        "home.py",
        title="Home",
        icon=":material/home:"
    ),
    st.Page(
        "information.py",
        title="Information",
        icon=":material/info:"
    )
]

page = st.navigation(pages)
page.run()

