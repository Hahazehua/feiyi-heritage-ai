# HAHA Competition Demo

## Start locally

From the project root:

```powershell
python -m pip install -e .[dev]
python -m streamlit run app.py
```

Open `http://localhost:8501`. The core demo works without an API key by using deterministic fallbacks. Optional live AI requires locally configured credentials; never display or commit them.

## Presenter setup

1. Use a desktop browser at approximately 1440 px.
2. Open the Buyer page and choose Chinese or English from the global selector.
3. Click **比赛演示 / Competition Demo**.
4. Use **重置演示 / Reset Demo** before a new presentation. Reset clears transient session flow only; it does not delete saved campaign repository data or other user records.
5. Keep review-only execution traces disabled unless a judge explicitly asks for technical evidence.

## Recommended 5–7 minute story

### 1. Explain HAHA

Use the landing and About page to frame the platform:

> Most heritage platforms digitize products. HAHA helps digitize the artisan, structures trusted cultural knowledge, builds market campaigns, protects cultural authenticity, and connects the result with real buyer demand.

Show the **Digitize → Grow → Connect** story.

### 2. Start with real Buyer demand

Use a concise prompt such as:

```text
我想给一位美国教授准备一份 150 美元以内、有中国文化特色、典雅且方便携带的毕业礼物。
```

English alternative:

```text
I need an elegant Chinese cultural graduation gift for a US professor, under $150 and easy to carry overseas.
```

Highlight that HAHA converts natural language into an editable gift brief.

### 3. Show grounded recommendations

Point out:

- why each item fits;
- cultural meaning and Heritage Passport evidence;
- demo/commercial-verification labels;
- the visual distinction between recommendation products and museum references;
- comparison without changing deterministic ranking.

Do not describe demo prices, shipping, inventory, or lead times as verified merchant commitments.

### 4. Move to Artisan Studio

Switch to **我是手艺人 / I'm an Artisan**.

Explain the flow:

```text
Artisan knowledge → HAHA structures it → Artisan confirms facts → Heritage Passport
```

Show that completeness and verification are separate metrics. Unknown fields remain visible and neutral.

### 5. Open Growth Studio

Choose **Growth Studio** and a demo product. Use a goal such as:

```text
Help this product reach corporate gift buyers in the United States.
```

Keep **Interface Language** separate from **Campaign Language**.

For a predictable Guardian demonstration, enable the labelled Guardian revision fixture. It adds an explicitly marked unsupported phrase only to the preserved raw demo draft.

### 6. Run the AI Growth Team

Run **Run HAHA Growth Team** and narrate the product flow rather than technical logs:

```text
Market → Strategy → Creative → Guardian → Revision
```

Show:

- market opportunity cards and the AI-assessment disclaimer;
- the actionable strategy brief;
- channel-grouped creative assets;
- Guardian supported-claim, revision, and risk summary;
- raw versus revised wording;
- the maximum two-revision safety limit.

### 7. Save and reopen

Save the campaign, then reopen it from **Saved campaigns**. Explain that raw AI, Guardian-revised, and human-edited versions remain distinguishable.

End by returning to the platform story: trusted artisan knowledge feeds responsible growth work, while only separately eligible catalogue products can appear to Buyers.

## Claims to avoid

Do not claim that the prototype currently has:

- verified real merchants or artisan identities;
- live inventory, quotations, shipping, or production capacity;
- external market-size research;
- external social publishing;
- completed orders, revenue, or conversion evidence;
- automatic product publication from Artisan Studio or Growth Studio.

## Recovery during a demo

- If optional AI is unavailable, continue with deterministic fallback output.
- If campaign storage is unavailable, keep the current draft open and explain that nothing unsafe was published.
- If a page becomes cluttered from prior actions, use **Reset Demo**.
- If browser state is stale, refresh the page; saved repository campaigns are independent of the transient competition-demo step.

