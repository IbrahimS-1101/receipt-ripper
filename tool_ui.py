from html import escape

import streamlit as st


def tool_header(title, description, description_ar):
    st.html("""
        <style>
        .st-key-tool_intro {
            margin-bottom: 0.65rem;
        }
        .st-key-tool_intro::before {
            content: "";
            display: block;
            width: 3rem;
            height: 3px;
            border-radius: 999px;
            background-color: currentColor;
            margin-bottom: 0.2rem;
        }
        .st-key-tool_intro h1 {
            font-size: clamp(2rem, 5vw, 3.35rem);
            letter-spacing: -0.045em;
            line-height: 1.05;
            padding-bottom: 0.2rem;
        }
        .st-key-tool_intro p {
            max-width: 58ch;
            font-size: 1.06rem;
            line-height: 1.55;
        }
        </style>
    """)
    with st.container(key="tool_intro"):
        st.title(title, anchor=False)
        st.write(description)
        arabic_intro(description_ar)


def arabic_intro(description):
    st.html(f"""
        <style>
        .tool-intro-ar {{
            border-inline-start: 2px solid color-mix(in srgb, currentColor 24%, transparent);
            border-radius: 6px;
            background: color-mix(in srgb, currentColor 4%, transparent);
            padding: 0.55rem 0.8rem;
            margin-top: 0.15rem;
            font-size: 0.96rem;
            line-height: 1.8;
            text-align: start;
        }}
        </style>
        <div class="tool-intro-ar" lang="ar" dir="rtl">{escape(description)}</div>
    """)


def support_footer():
    st.html("""
        <style>
        .tool-footer {
            border-top: 1px solid color-mix(in srgb, currentColor 18%, transparent);
            margin-top: 1.25rem;
            padding-top: 0.85rem;
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            gap: 0.35rem 1rem;
            font-size: 0.82rem;
        }
        .tool-footer a {
            color: inherit;
            text-underline-offset: 0.18em;
        }
        .tool-footer .tool-support {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            min-height: 36px;
            padding: 0 0.75rem;
            border: 1px solid color-mix(in srgb, currentColor 25%, transparent);
            border-radius: 999px;
            text-decoration: none;
            font-weight: 550;
        }
        .tool-footer .tool-support:hover {
            background: color-mix(in srgb, currentColor 8%, transparent);
            text-decoration: underline;
        }
        .tool-footer a:focus-visible {
            outline: 2px solid currentColor;
            outline-offset: 3px;
        }
        </style>
        <footer class="tool-footer">
            <span>Made by Ibrahim Samir · <a href="https://takea5.com"
                target="_blank" rel="noopener noreferrer">Take A 5</a></span>
            <a class="tool-support" href="https://buymeacoffee.com/isamir"
                target="_blank" rel="noopener noreferrer">
                <span aria-hidden="true">☕</span> Buy me a coffee
            </a>
        </footer>
    """)
