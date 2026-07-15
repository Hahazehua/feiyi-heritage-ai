def test_streamlit_and_core_modules_import() -> None:
    import streamlit  # noqa: F401

    import app  # noqa: F401
    from heritagelink import (  # noqa: F401
        config,
        content,
        conversation_state,
        customization_concept,
        dialogue_manager,
        dialogue_prompt,
        inquiry,
        llm_client,
        progressive_recommender,
        request_parser,
    )
