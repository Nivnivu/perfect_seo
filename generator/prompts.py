from tools.site_context import format_context_for_prompt


def build_blog_prompt(topic_data, config, site_context=None):
    """Build the Gemini prompt for generating a new SEO blog post in Hebrew."""
    target_kw = topic_data["target_keyword"]
    related_kws = ", ".join(topic_data.get("related_keywords", [])[:15])
    paa = "\n".join(f"- {q}" for q in topic_data.get("paa_questions", []))
    serp_titles = "\n".join(f"- {t}" for t in topic_data.get("serp_titles", []))
    comp = topic_data.get("competitor_summary", {})
    avg_words = comp.get("avg_word_count", 1500)
    common_headings = ", ".join(comp.get("common_headings", [])[:10])
    common_keywords = ", ".join(comp.get("common_keywords", [])[:20])
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]

    # Site context block (brand voice, products, internal links)
    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context, topic=target_kw)

    return f"""אתה כותב תוכן SEO מומחה עבור האתר "{site_name}" ({domain}).

{context_block}

=== משימה ===
כתוב פוסט בלוג מותאם SEO בעברית. הפוסט חייב להיות ספציפי ל-{site_name} ולהזכיר את המותגים והמוצרים שלנו.

=== מילת מפתח ראשית ===
{target_kw}

=== מילות מפתח קשורות לשלב באופן טבעי ===
{related_kws}

=== שאלות שאנשים שואלים (ענה עליהן בפוסט) ===
{paa if paa else "לא נמצאו שאלות - צור שאלות FAQ רלוונטיות"}

=== כותרות מתחרים (כתוב משהו טוב יותר) ===
{serp_titles if serp_titles else "לא נמצאו תוצאות - צור כותרת מושכת"}

=== ניתוח מתחרים ===
- אורך ממוצע של מתחרים: {avg_words} מילים (כתוב לפחות {int(avg_words * 1.2)} מילים)
- כותרות משנה נפוצות: {common_headings if common_headings else "לא זמין"}
- מילות מפתח נפוצות: {common_keywords if common_keywords else "לא זמין"}

=== זווית ייחודית (מה שהמתחרים לא מכסים) ===
המתחרים מכסים את כותרות המשנה הנפוצות שלמעלה — אבל זה בדיוק מה שכולם כותבים.
חייב לכלול לפחות סקציה אחת שהמתחרים לא מכסים — נושא-משנה, זווית או תובנה שאינה מופיעה ברשימת כותרות המתחרים.
דוגמאות לזוויות ייחודיות: ניסיון מהשטח עם לקוחות, השוואה בין מוצרים ספציפיים מהקטלוג שלנו, טעויות נפוצות שרואים בפועל, מדריך בחירה לפי סוג חיה/גיל/מצב בריאותי בהתבסס על המוצרים שאנחנו מוכרים.
שלב לפחות 2 סמני E-E-A-T בגוף הפוסט — ניסיון ישיר וסמכות: לדוגמה "מניסיוננו עם לקוחות...", "בהשוואה שערכנו...", "לקוחות שרכשו... מדווחים ש...". הצב אותם בנקודות טבעיות בתוך הסקציות הרלוונטיות.
נצל את קטלוג המוצרים הייחודי של {site_name}: הצע המלצות ספציפיות עם שמות מוצרים ומותגים מהאתר שלנו — ערך שאתרי תוכן כלליים לא יכולים לספק.

=== אותות GEO (לציטוט על ידי AI) ===
תוכן שמצוטט על ידי Gemini, ChatGPT ו-Perplexity חייב להיות עשיר בעובדות שניתן לאמת.
כלול בגוף הפוסט:
• לפחות 3 סטטיסטיקות/מספרים ספציפיים — דוגמה: "73% מהכלבים מעל גיל 7 מפתחים...", "מחקר 2023 מצא ש-X%...", "כלבים בוגרים זקוקים ל-XX גרם חלבון ביום"
• לפחות 2 הצהרות דקלרטיביות חד-משמעיות שניתן לצטט ישירות, ללא סייגים: "X הוא...", "הכלל הוא ש-Y...", "הדרך הנכונה ל-Z היא..."
• ישויות מוגדרות (Named Entities) לעיגון סמכות: שמות מותגים ספציפיים, מחקרים/ארגונים, שנים — לדוגמה: Royal Canin, Hill's Science Diet, AAFCO, מחקר מ-2022, ד"ר [שם] וכו'
מטרה: AI יחלץ ויצטט עובדות ספציפיות ומדידות — לא הכללות. ככל שהמספר ספציפי יותר, כך גדל הסיכוי לציטוט.

=== דרישות ===
1. כותרת (H1): כלול את מילת המפתח הראשית. הפוך אותה למושכת קליקים.
2. תיאור מטא: 150-160 תווים, כלול מילת מפתח ראשית, קריאה לפעולה.
3. מבנה: השתמש בכותרות H2 ו-H3. כל H2 צריך לכוון למילת מפתח קשורה.
4. בלוק תשובה ישירה (AI Overview): מיד לאחר פסקת הפתיחה, כלול:
   === תשובה ישירה (לציטוט AI) ===
   [תשובה ישירה לשאילתה הראשית — בדיוק 40-60 מילים בעברית]
   חובה: בדיוק 40-60 מילים, משפט שלם ועצמאי, עונה על השאילתה הראשית ללא הקדמה. מיועד לציטוט על ידי AI Overviews בגוגל.
5. ענה על שאלות "אנשים שואלים גם" באופן טבעי בתוך החלקים הרלוונטיים.
6. אורך: כוון ל-{int(avg_words * 1.2)} מילים לפחות.
7. כלול חלק FAQ בסוף עם השאלות הנפוצות. כל תשובת FAQ: בדיוק 2-3 משפטים (40-60 מילים) — תשובה עצמאית ומלאה, מיועדת לחילוץ על ידי AI Overviews.
8. קישורים פנימיים: שלב 3-5 קישורים פנימיים לדפים אמיתיים באתר (מרשימת הדפים שלמעלה). השתמש בטקסט עוגן טבעי.
9. הזכר מוצרים ומותגים ספציפיים של {site_name} כשזה רלוונטי לנושא.
10. טון: התאם לקול המותג המתואר בסעיף ההקשר. לא מכירתי.
11. שפה: כתוב הכל בעברית.

=== פורמט קישורים (חשוב!) ===
כל קישור בגוף הפוסט חייב להיות בפורמט markdown:
[טקסט עוגן](https://url-מלא)

דוגמה נכונה: מומלץ לנסות את [מזון Natural Greatness לכלבים](https://pawly.co.il/dogs)
דוגמה שגויה: מומלץ לנסות את מזון Natural Greatness לכלבים -> https://pawly.co.il/dogs
דוגמה שגויה: מומלץ לנסות את מזון Natural Greatness לכלבים (https://pawly.co.il/dogs)

אל תשתמש בחצים (->) או בסוגריים רגילים לקישורים. רק [טקסט](URL).

=== פורמט פלט ===
החזר את הפוסט במבנה הבא:

TITLE: [כותרת H1]
META_DESCRIPTION: [תיאור מטא]
SLUG: [slug באנגלית מתורגמת]

---

[פסקת פתיחה — 2-3 משפטים]

=== תשובה ישירה (לציטוט AI) ===
[40-60 מילים שעונות ישירות על השאילתה הראשית — משפט עצמאי ומלא]

[שאר הפוסט בעברית עם כותרות markdown (## ל-H2, ### ל-H3) וקישורים בפורמט [טקסט](URL)]

---

IMAGE_SUGGESTIONS:
1. [תיאור + טקסט alt]
2. [תיאור + טקסט alt]
3. [תיאור + טקסט alt]
"""


def build_edit_prompt(post_data, competitor_summary, all_keywords, config, site_context=None):
    """Build the Gemini prompt for suggesting edits to an existing blog post."""
    missing_kws = ", ".join(post_data.get("keywords_missing", [])[:10])
    current_wc = post_data.get("word_count", 0)
    target_wc = competitor_summary.get("avg_word_count", 1500)
    content_preview = post_data.get("content_text", "")[:2000]
    headings = post_data.get("headings", {})
    h2s = ", ".join(headings.get("h2", []))
    site_name = config["site"]["name"]

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context)

    return f"""אתה עורך תוכן SEO עבור האתר "{site_name}".
נתח את הפוסט הקיים ותן הצעות שיפור ספציפיות בעברית.

{context_block}

=== פוסט קיים ===
כותרת: {post_data.get('title', 'לא ידוע')}
URL: {post_data.get('url', 'לא ידוע')}
אורך נוכחי: {current_wc} מילים
כותרות H2 נוכחיות: {h2s if h2s else "אין"}

תצוגה מקדימה של התוכן:
{content_preview}

=== בעיות שזוהו ===
- אורך נוכחי ({current_wc} מילים) לעומת ממוצע מתחרים ({target_wc} מילים)
- מילות מפתח חסרות: {missing_kws if missing_kws else "אין"}
- סיבות לעדכון: {', '.join(post_data.get('update_reasons', []))}

=== הנחיות ===
תן הצעות ספציפיות וניתנות ליישום:
1. חלקים חדשים להוסיף (עם כותרות H2 ותקציר תוכן) לכיסוי מילות מפתח חסרות.
2. פסקאות להרחיב עם פרטים נוספים.
3. מילות מפתח חסרות ואיפה/איך לשלב אותן.
4. שיפור תיאור מטא אם נדרש.
5. קישורים פנימיים לדפים אמיתיים באתר (מרשימת הדפים למעלה).
6. שאלות FAQ להוסיף בתחתית.
7. הזכרת מוצרים ומותגים ספציפיים של {site_name} כשרלוונטי.

כל קישור חייב להיות בפורמט markdown: [טקסט עוגן](https://url-מלא)

כתוב את כל ההצעות בעברית. היה ספציפי - אל תגיד "הוסף עוד תוכן", אמור בדיוק איזה תוכן להוסיף ואיפה.
"""


def build_rewrite_prompt(post_data, competitor_summary, all_keywords, config, site_context=None):
    """Build the Gemini prompt for rewriting and expanding an existing blog post."""
    missing_kws = ", ".join(post_data.get("keywords_missing", [])[:10])
    related_kws = ", ".join(all_keywords[:15])
    current_wc = post_data.get("word_count", 0)
    target_wc = int(competitor_summary.get("avg_word_count", 1500) * 1.2)
    content_text = post_data.get("content_text", "")[:3000]
    headings = post_data.get("headings", {})
    h2s = ", ".join(headings.get("h2", []))
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]

    # GSC intelligence block
    gsc_context = post_data.get("gsc_context", {})
    gsc_category = gsc_context.get("category", "")
    ranking_queries = gsc_context.get("top_queries", [])
    gsc_metrics = gsc_context.get("metrics", {})

    # Title: for not_indexed pages, title change is safe (no rankings at risk) and often necessary.
    # For all other pages: NEVER change the title — it's the URL slug.
    if gsc_category == "not_indexed":
        title_instruction = (
            "כותרת (H1): צור כותרת חדשה שמטרגטת שאילתת חיפוש ספציפית שגולשים מחפשים. "
            "הכותרת הנוכחית כנראה לא תואמת חיפושים אמיתיים — החלף אותה בביטוי חיפוש ממוקד."
        )
    else:
        title_instruction = "כותרת (H1): השתמש בכותרת המקורית בדיוק כפי שהיא — שינוי כותרת משנה את ה-URL ומוחק את הדירוג בגוגל."

    gsc_block = ""
    if gsc_category == "not_indexed":
        gsc_block = f"""
╔══════════════════════════════════════════════════════════╗
║  ⚠️  CRITICAL: דף זה לא אינדוקס על ידי גוגל מעולם      ║
╚══════════════════════════════════════════════════════════╝

הסיבה הנפוצה ביותר לאי-אינדוקס: תוכן שיווקי/B2B שלא עונה לשאלות גולשים אמיתיים.
גוגל מתעלם מתוכן שנראה כמו קמפיין פרסומי ולא כתשובה לחיפוש.

=== מה גוגל רוצה לראות (Helpful Content) ===
• תוכן שעונה על שאלות ספציפיות של גולשים (מה גולשים מחפשים?)
• מידע מעשי, ספציפי, עם דוגמאות ומספרים
• NOT: "הפלטפורמה שלנו...", "שותפות אסטרטגית...", "אנחנו מובילים..."
• NOT: תוכן מכוון לחנויות/B2B אם הגולשים הם צרכנים

=== מילות מפתח לטרגוט (ממתחרים מובילים) ===
{related_kws}

=== כללי שכתוב לדף לא-אינדוקס ===
1. כותרת חדשה: טרגט שאילתת חיפוש ספציפית (מה גולשים מחפשים?)
2. פסקת פתיחה: ענה על השאלה המרכזית מיד — אל תתחיל בסיפור החברה
3. גוף: מידע מעשי, טבלאות השוואה, דוגמאות, המלצות ספציפיות
4. FAQ: שאלות שגולשים שואלים בגוגל על הנושא"""

    elif ranking_queries:
        queries_list = "\n".join(f"- {q}" for q in ranking_queries[:12])
        gsc_block = f"""
╔══════════════════════════════════════════════════════════╗
║  ⚠️  אזהרת SEO קריטית — שמור על שאילתות הדירוג הנוכחיות  ║
╚══════════════════════════════════════════════════════════╝

העמוד הזה כרגע מדורג בגוגל ומקבל תנועה אורגנית.
כל שינוי שיסיר את הביטויים שגוגל כבר מקשר לעמוד הזה — יהרוס את הדירוג.

=== שאילתות שגוגל כבר מקשר לעמוד זה (חובה לשמר!) ===
{queries_list}

חוק ברזל: כל אחת מהשאילתות האלה חייבת להופיע באופן טבעי בטקסט המשוכתב.
עדיפות: שלב אותן בכותרות H2/H3, בפסקת הפתיחה, ובחלק ה-FAQ.

מיקום נוכחי: {gsc_metrics.get('position', '?')} | קליקים: {gsc_metrics.get('clicks', 0)} | חשיפות: {gsc_metrics.get('impressions', 0)} | CTR: {gsc_metrics.get('ctr_pct', 0)}%"""

        if gsc_category == "page2_opportunity":
            gsc_block += f"""

⚡ מטרת העדכון: דחיפה מעמוד 2 לעמוד 1 (מיקום {gsc_metrics.get('position', '?')}).
אסטרטגיה: הרחב כל שאילתה מהרשימה לסקציה שלמה עם H2, פסקאות, דוגמאות ו-FAQ ייעודי.
אל תוסיף נושאים חדשים שאינם בשאילתות — עמק בקיים, אל תרחב לצדדים."""
        elif gsc_category == "ctr_opportunity":
            gsc_block += """

⚡ מטרת העדכון: שיפור CTR בלבד.
הגוף מדורג טוב — אל תשנה את המבנה. שפר רק את תיאור המטא: הפוך אותו ספציפי, מספרי ומושך."""

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context, topic=post_data.get("title", ""))

    return f"""אתה כותב תוכן SEO מומחה עבור האתר "{site_name}" ({domain}).
שכתב והרחב את הפוסט הקיים.

{context_block}
{gsc_block}

=== משימה ===
שכתב את הפוסט הקיים מחדש בצורה מורחבת ומשופרת. שמור על הנושא המקורי אבל הפוך אותו לטוב יותר.
הפוסט חייב להיות ספציפי ל-{site_name} ולהזכיר מותגים ומוצרים רלוונטיים.

=== פוסט קיים ===
כותרת: {post_data.get('title', 'לא ידוע')}
אורך נוכחי: {current_wc} מילים
כותרות H2 נוכחיות: {h2s if h2s else "אין"}

תוכן נוכחי:
{content_text}

=== בעיות לתקן ===
- אורך נוכחי ({current_wc} מילים) נמוך מדי — כתוב לפחות {target_wc} מילים
- מילות מפתח חסרות שחייבות להיכלל: {missing_kws if missing_kws else "אין"}
- סיבות לעדכון: {', '.join(post_data.get('update_reasons', []))}

=== מילות מפתח קשורות לשלב באופן טבעי ===
{related_kws}

=== ניתוח מתחרים ===
- אורך ממוצע: {competitor_summary.get('avg_word_count', 1500)} מילים
- כותרות משנה נפוצות: {', '.join(competitor_summary.get('common_headings', [])[:10])}
- מילות מפתח נפוצות: {', '.join(competitor_summary.get('common_keywords', [])[:20])}

=== זווית ייחודית (מה שהמתחרים לא מכסים) ===
המתחרים מכסים את כותרות המשנה הנפוצות שלמעלה — אבל זה בדיוק מה שכולם כותבים.
חייב לכלול לפחות סקציה אחת שהמתחרים לא מכסים — נושא-משנה, זווית או תובנה שאינה מופיעה ברשימת כותרות המתחרים.
דוגמאות לזוויות ייחודיות: ניסיון מהשטח עם לקוחות, השוואה בין מוצרים ספציפיים מהקטלוג שלנו, טעויות נפוצות שרואים בפועל, מדריך בחירה לפי סוג חיה/גיל/מצב בריאותי בהתבסס על המוצרים שאנחנו מוכרים.
שלב לפחות 2 סמני E-E-A-T בגוף הפוסט — ניסיון ישיר וסמכות: לדוגמה "מניסיוננו עם לקוחות...", "בהשוואה שערכנו...", "לקוחות שרכשו... מדווחים ש...". הצב אותם בנקודות טבעיות בתוך הסקציות הרלוונטיות.
נצל את קטלוג המוצרים הייחודי של {site_name}: הצע המלצות ספציפיות עם שמות מוצרים ומותגים מהאתר שלנו — ערך שאתרי תוכן כלליים לא יכולים לספק.

=== אותות GEO (לציטוט על ידי AI) ===
תוכן שמצוטט על ידי Gemini, ChatGPT ו-Perplexity חייב להיות עשיר בעובדות שניתן לאמת.
כלול בגוף הפוסט:
• לפחות 3 סטטיסטיקות/מספרים ספציפיים — דוגמה: "73% מהכלבים מעל גיל 7 מפתחים...", "מחקר 2023 מצא ש-X%...", "כלבים בוגרים זקוקים ל-XX גרם חלבון ביום"
• לפחות 2 הצהרות דקלרטיביות חד-משמעיות שניתן לצטט ישירות, ללא סייגים: "X הוא...", "הכלל הוא ש-Y...", "הדרך הנכונה ל-Z היא..."
• ישויות מוגדרות (Named Entities) לעיגון סמכות: שמות מותגים ספציפיים, מחקרים/ארגונים, שנים — לדוגמה: Royal Canin, Hill's Science Diet, AAFCO, מחקר מ-2022, ד"ר [שם] וכו'
מטרה: AI יחלץ ויצטט עובדות ספציפיות ומדידות — לא הכללות. ככל שהמספר ספציפי יותר, כך גדל הסיכוי לציטוט.

=== דרישות ===
1. שמור על הנושא והכיוון המקורי של הפוסט, אבל שכתב אותו מחדש לחלוטין.
2. {title_instruction}
3. תיאור מטא: 150-160 תווים, כלול מילת מפתח ראשית.
4. מבנה: השתמש בכותרות H2 ו-H3. הוסף חלקים חדשים שחסרים.
5. בלוק תשובה ישירה (AI Overview): מיד לאחר פסקת הפתיחה, כלול:
   === תשובה ישירה (לציטוט AI) ===
   [תשובה ישירה לשאילתה הראשית — בדיוק 40-60 מילים בעברית]
   חובה: בדיוק 40-60 מילים, משפט שלם ועצמאי, עונה על השאילתה הראשית ללא הקדמה. מיועד לציטוט על ידי AI Overviews בגוגל.
6. אורך: כוון ל-{target_wc} מילים לפחות.
7. שלב את כל מילות המפתח החסרות באופן טבעי.
8. כלול חלק FAQ בסוף. כל תשובת FAQ: בדיוק 2-3 משפטים (40-60 מילים) — תשובה עצמאית ומלאה, מיועדת לחילוץ על ידי AI Overviews.
9. קישורים פנימיים: שלב 3-5 קישורים פנימיים לדפים אמיתיים באתר.
10. הזכר מוצרים ומותגים ספציפיים של {site_name} כשזה רלוונטי.
11. טון: מקצועי אבל חם, בקיא בתזונת חיות מחמד. לא מכירתי.
12. שפה: כתוב הכל בעברית.

=== פורמט קישורים (חשוב!) ===
כל קישור בגוף הפוסט חייב להיות בפורמט markdown:
[טקסט עוגן](https://url-מלא)

דוגמה נכונה: מומלץ לנסות את [מזון Natural Greatness לכלבים](https://pawly.co.il/dogs)
דוגמה שגויה: מומלץ לנסות את מזון Natural Greatness לכלבים -> https://pawly.co.il/dogs
דוגמה שגויה: מומלץ לנסות את מזון Natural Greatness לכלבים (https://pawly.co.il/dogs)

אל תשתמש בחצים (->) או בסוגריים רגילים לקישורים. רק [טקסט](URL).

=== פורמט פלט ===
החזר את הפוסט במבנה הבא:

TITLE: [כותרת H1]
META_DESCRIPTION: [תיאור מטא]
SLUG: [slug באנגלית מתורגמת]

---

[פסקת פתיחה — 2-3 משפטים]

=== תשובה ישירה (לציטוט AI) ===
[40-60 מילים שעונות ישירות על השאילתה הראשית — משפט עצמאי ומלא]

[שאר הפוסט בעברית עם כותרות markdown (## ל-H2, ### ל-H3) וקישורים בפורמט [טקסט](URL)]

---

IMAGE_SUGGESTIONS:
1. [תיאור + טקסט alt]
2. [תיאור + טקסט alt]
"""


def build_fix_prompt(current_post, user_feedback, config):
    """Build a prompt to apply minor fixes to a blog post based on user feedback."""
    site_name = config["site"]["name"]

    return f"""אתה עורך תוכן עבור האתר "{site_name}".
קיבלת פידבק מהמשתמש על הפוסט הבא. בצע את התיקונים המבוקשים.

=== הפוסט הנוכחי ===
{current_post}

=== פידבק מהמשתמש ===
{user_feedback}

=== הנחיות ===
1. בצע רק את התיקונים שהמשתמש ביקש. אל תשנה דברים אחרים.
2. שמור על אותו מבנה ופורמט פלט (TITLE, META_DESCRIPTION, SLUG, ---, גוף הפוסט, ---).
3. כל קישור חייב להיות בפורמט markdown: [טקסט עוגן](https://url-מלא)
4. שמור על אותו אורך ואיכות.

=== פורמט פלט ===
החזר את הפוסט המתוקן במבנה זהה:

TITLE: [כותרת H1]
META_DESCRIPTION: [תיאור מטא]
SLUG: [slug באנגלית]

---

[פוסט מתוקן]

---

IMAGE_SUGGESTIONS:
1. [תיאור + טקסט alt]
2. [תיאור + טקסט alt]
"""


def build_static_page_prompt(page_title, page_id, current_text, config, site_context=None, gsc_context=None):
    """Build the Gemini prompt for rewriting a static page with SEO improvements."""
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context)

    # GSC intelligence block — same logic as build_rewrite_prompt
    gsc_block = ""
    if gsc_context:
        gsc_category = gsc_context.get("category", "")
        ranking_queries = gsc_context.get("top_queries", [])
        gsc_metrics = gsc_context.get("metrics", {})

        if ranking_queries:
            queries_list = "\n".join(f"- {q}" for q in ranking_queries[:12])
            gsc_block = f"""
╔══════════════════════════════════════════════════════════╗
║  ⚠️  אזהרת SEO קריטית — שמור על שאילתות הדירוג הנוכחיות  ║
╚══════════════════════════════════════════════════════════╝

העמוד הזה כרגע מדורג בגוגל ומקבל תנועה אורגנית.
כל שינוי שיסיר את הביטויים שגוגל כבר מקשר לעמוד הזה — יהרוס את הדירוג.

=== שאילתות שגוגל כבר מקשר לעמוד זה (חובה לשמר!) ===
{queries_list}

חוק ברזל: כל אחת מהשאילתות האלה חייבת להופיע באופן טבעי בטקסט המשוכתב.
מיקום נוכחי: {gsc_metrics.get('position', '?')} | קליקים: {gsc_metrics.get('clicks', 0)} | חשיפות: {gsc_metrics.get('impressions', 0)}"""

            if gsc_category == "page2_opportunity":
                gsc_block += f"""

⚡ מטרת העדכון: דחיפה מעמוד 2 לעמוד 1 (מיקום {gsc_metrics.get('position', '?')}).
הרחב כל שאילתה מהרשימה לסקציה שלמה עם H2 ייעודי."""

    return f"""אתה כותב תוכן SEO מומחה עבור האתר "{site_name}" ({domain}).
שכתב את תוכן העמוד הסטטי הבא בצורה משופרת, עשירה יותר ומותאמת SEO.

{context_block}
{gsc_block}

=== פרטי העמוד ===
כותרת נוכחית: {page_title}
מזהה עמוד: {page_id}

=== תוכן נוכחי ===
{current_text}

=== אותות GEO (לציטוט על ידי AI) ===
תוכן שמצוטט על ידי Gemini, ChatGPT ו-Perplexity חייב להיות עשיר בעובדות שניתן לאמת.
כלול בגוף העמוד:
• לפחות 3 סטטיסטיקות/מספרים ספציפיים — דוגמה: "73% מהכלבים מעל גיל 7 מפתחים...", "מחקר 2023 מצא ש-X%...", "כלבים בוגרים זקוקים ל-XX גרם חלבון ביום"
• לפחות 2 הצהרות דקלרטיביות חד-משמעיות שניתן לצטט ישירות, ללא סייגים: "X הוא...", "הכלל הוא ש-Y...", "הדרך הנכונה ל-Z היא..."
• ישויות מוגדרות (Named Entities) לעיגון סמכות: שמות מותגים ספציפיים, מחקרים/ארגונים, שנים — לדוגמה: Royal Canin, Hill's Science Diet, AAFCO, מחקר מ-2022, ד"ר [שם] וכו'
מטרה: AI יחלץ ויצטט עובדות ספציפיות ומדידות — לא הכללות. ככל שהמספר ספציפי יותר, כך גדל הסיכוי לציטוט.

=== דרישות ===
1. שכתב את התוכן בצורה מקצועית, עשירה ומשכנעת יותר.
2. שמור על המשמעות והמטרה המקורית של העמוד.
3. הוסף תוכן רלוונטי שחסר — הרחב נקודות חשובות.
4. השתמש בכותרות H2 ו-H3 לארגון התוכן.
5. שלב מילות מפתח רלוונטיות ל-{site_name} באופן טבעי.
6. שלב 2-3 קישורים פנימיים לדפים אמיתיים באתר.
7. הטון: מקצועי, חם, ומעודד. מותאם ל-{site_name}.
8. שפה: כתוב הכל בעברית.
9. אורך: לפחות כפול מהתוכן הנוכחי.

=== פורמט קישורים (חשוב!) ===
כל קישור בגוף התוכן חייב להיות בפורמט markdown:
[טקסט עוגן](https://url-מלא)

אל תשתמש בחצים (->) או בסוגריים רגילים לקישורים. רק [טקסט](URL).

=== פורמט פלט ===
החזר את התוכן במבנה הבא:

TITLE: [כותרת העמוד המשופרת]

---

[תוכן העמוד המלא בעברית עם כותרות markdown (## ל-H2, ### ל-H3)]

---
"""


def build_product_prompt(product_data, gsc_context, config, site_context=None):
    """
    Build a Gemini prompt to SEO-optimize a product page.
    Output: META_DESCRIPTION + full HTML content.
    The technical specs (ingredients, nutrition) must be preserved exactly.
    """
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]
    title = product_data.get("title", "")
    current_text = product_data.get("content_text", "")  # already stripped of external images

    gsc_category = gsc_context.get("category", "not_indexed")
    ranking_queries = gsc_context.get("top_queries", [])
    gsc_metrics = gsc_context.get("metrics", {})

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context, topic=title)

    # GSC block — same pattern as blog rewrite
    gsc_block = ""
    if ranking_queries:
        queries_list = "\n".join(f"- {q}" for q in ranking_queries[:10])
        gsc_block = f"""
╔══════════════════════════════════════════════════════════╗
║  ⚠️  עמוד זה מדורג בגוגל — שמור על שאילתות הדירוג     ║
╚══════════════════════════════════════════════════════════╝
שאילתות שגוגל כבר מקשר לעמוד זה (חובה לשלב בטקסט):
{queries_list}
מיקום: {gsc_metrics.get('position','?')} | קליקים: {gsc_metrics.get('clicks',0)} | חשיפות: {gsc_metrics.get('impressions',0)}"""

    elif gsc_category == "not_indexed":
        gsc_block = """
⚠️  עמוד זה אינו מאונדקס בגוגל — כתוב תוכן שמענה על שאלות אמיתיות של גולשים.
התמקד בתועלות המוצר לחיות המחמד, לא בפרסום מותג."""

    # Internal links from site context
    blog_url = config["site"].get("blog_url", f"https://{domain}/blog")

    return f"""אתה מומחה SEO לאתר "{site_name}" ({domain}).
עמוד המוצר הזה נמצא בכתובת: https://{domain}/products/{product_data.get('slug','')}

{context_block}
{gsc_block}

=== המוצר ===
שם המוצר (כותרת H1 — אל תשנה): {title}

=== תוכן נוכחי (טקסט בלבד) ===
{current_text}

=== משימה ===
שפר את תוכן עמוד המוצר לצורך SEO. שמור את הנתונים הטכניים (הרכב, ערכים תזונתיים) בדיוק כפי שהם.

=== אותות GEO (לציטוט על ידי AI) ===
תוכן שמצוטט על ידי Gemini, ChatGPT ו-Perplexity חייב להיות עשיר בעובדות שניתן לאמת.
כלול בגוף העמוד:
• לפחות 3 סטטיסטיקות/מספרים ספציפיים — דוגמה: "73% מהכלבים מעל גיל 7 מפתחים...", "מחקר 2023 מצא ש-X%...", "כלבים בוגרים זקוקים ל-XX גרם חלבון ביום"
• לפחות 2 הצהרות דקלרטיביות חד-משמעיות שניתן לצטט ישירות, ללא סייגים: "X הוא...", "הכלל הוא ש-Y...", "הדרך הנכונה ל-Z היא..."
• ישויות מוגדרות (Named Entities) לעיגון סמכות: שמות מותגים ספציפיים, מחקרים/ארגונים, שנים — לדוגמה: Royal Canin, Hill's Science Diet, AAFCO, מחקר מ-2022, ד"ר [שם] וכו'
מטרה: AI יחלץ ויצטט עובדות ספציפיות ומדידות — לא הכללות. ככל שהמספר ספציפי יותר, כך גדל הסיכוי לציטוט.

=== דרישות ===
1. כתוב פסקת פתיחה SEO (3-4 משפטים): מה המוצר, למי מתאים, היתרון העיקרי.
2. שמור את הנתונים הטכניים המקוריים (הרכב, ערכים תזונתיים, אנרגיה, תוספים, טבלת האכלה) בדיוק ללא שינוי.
3. הוסף סקציית "יתרונות המוצר" עם 4-5 נקודות בעברית.
4. הוסף 2-3 שאלות נפוצות (FAQ) רלוונטיות.
5. הוסף 2 קישורים פנימיים לבלוג: [טקסט קישור]({blog_url}/slug-רלוונטי)
6. אל תמציא נתונים תזונתיים שאינם בתוכן המקורי.
7. שפה: עברית בלבד. טון: מקצועי, חם, בקיא בתזונת חיות מחמד.

=== פורמט פלט ===
META_DESCRIPTION: [150-160 תווים — תיאור מושך הכולל שם המוצר ותועלת עיקרית]

---

[HTML מלא של עמוד המוצר — השתמש ב-<h2> לכותרות סקציות, <ul>/<li> לרשימות, <p> לפסקאות]

---
"""


def build_recovery_rewrite_prompt(post_data, ranking_queries, config, site_context=None):
    """
    Build a prompt specifically for recovering lost rankings.

    This is used when a post's content was rewritten by the engine and rankings dropped.
    The prompt reverse-engineers what Google expected from this page using the actual
    GSC queries it ranked for, then rewrites to match that intent precisely.

    ranking_queries: list of dicts [{query, clicks, impressions, ctr_pct, position}]
    """
    title = post_data.get("title", "")
    current_content = post_data.get("content_text", "") or post_data.get("subtitle", "")
    old_clicks = post_data.get("old_clicks", 0)
    old_impressions = post_data.get("old_impressions", 0)
    old_position = post_data.get("old_position", "?")
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context, topic=title)

    if ranking_queries:
        queries_with_stats = "\n".join(
            f"- \"{q['query']}\" (מיקום {q['position']}, {q['impressions']} חשיפות, {q['clicks']} קליקים)"
            for q in ranking_queries[:15]
        )
    else:
        queries_with_stats = "לא נמצאו נתוני שאילתות — כתוב תוכן כללי לנושא הכותרת"

    target_wc = max(1500, len(current_content.split()) if current_content else 1500)

    return f"""אתה מומחה שחזור SEO עבור האתר "{site_name}" ({domain}).
העמוד הבא דורג בגוגל וקיבל תנועה אורגנית, אך לאחר עדכון תוכן — הדירוג ירד.

{context_block}

╔══════════════════════════════════════════════════════════════╗
║  משימת שחזור: כתוב תוכן שיחזיר את הדירוג לעמוד זה          ║
╚══════════════════════════════════════════════════════════════╝

=== פרטי העמוד ===
כותרת: {title}
ביצועים לפני ירידה: {old_clicks} קליקים | {old_impressions} חשיפות | מיקום {old_position}

=== שאילתות שגוגל שיוך לעמוד זה — חובה לכסות את כולן ===
{queries_with_stats}

אלו הן השאילתות שגוגל "הבין" שהעמוד עונה עליהן.
הן מגדירות את כוונת הגולש שגוגל שייך לעמוד — כתוב תוכן שעונה עליהן ישירות ולעומק.

=== אסטרטגיית שחזור ===
1. צור H2 ייעודי לכל שאילתה מהרשימה (או קבץ שאילתות קרובות יחד)
2. כתוב 2-3 פסקאות תחת כל H2 שעונות לעומק על הכוונה מאחורי השאילתה
3. בלוק תשובה ישירה (AI Overview): מיד לאחר פסקת הפתיחה, כלול:
   === תשובה ישירה (לציטוט AI) ===
   [תשובה ישירה לשאילתה הראשית — בדיוק 40-60 מילים בעברית]
   חובה: בדיוק 40-60 מילים, משפט שלם ועצמאי, ללא הקדמה. מיועד לציטוט על ידי AI Overviews בגוגל.
4. כלול FAQ בתחתית עם כל השאילתות כשאלות. כל תשובת FAQ: בדיוק 2-3 משפטים (40-60 מילים) — תשובה עצמאית ומלאה, מיועדת לחילוץ על ידי AI Overviews.
5. השתמש במספרים, עובדות ספציפיות — גוגל מעדיף תוכן מדויק
6. שלב 3-5 קישורים פנימיים לדפים אמיתיים באתר

=== אותות GEO (לציטוט על ידי AI) ===
תוכן שמצוטט על ידי Gemini, ChatGPT ו-Perplexity חייב להיות עשיר בעובדות שניתן לאמת.
כלול בגוף הפוסט:
• לפחות 3 סטטיסטיקות/מספרים ספציפיים — דוגמה: "73% מהכלבים מעל גיל 7 מפתחים...", "מחקר 2023 מצא ש-X%...", "כלבים בוגרים זקוקים ל-XX גרם חלבון ביום"
• לפחות 2 הצהרות דקלרטיביות חד-משמעיות שניתן לצטט ישירות, ללא סייגים: "X הוא...", "הכלל הוא ש-Y...", "הדרך הנכונה ל-Z היא..."
• ישויות מוגדרות (Named Entities) לעיגון סמכות: שמות מותגים ספציפיים, מחקרים/ארגונים, שנים — לדוגמה: Royal Canin, Hill's Science Diet, AAFCO, מחקר מ-2022, ד"ר [שם] וכו'
מטרה: AI יחלץ ויצטט עובדות ספציפיות ומדידות — לא הכללות. ככל שהמספר ספציפי יותר, כך גדל הסיכוי לציטוט.

=== דרישות חובה ===
1. כותרת (H1): שמור על הכותרת המקורית בדיוק: {title}
   (שינוי כותרת = שינוי URL = 404 = איבוד כל הדירוג שנשמר)
2. תיאור מטא: 150-160 תווים, כולל מילת המפתח הראשית, קריאה לפעולה
3. אורך: לפחות {target_wc} מילים
4. שפה: עברית
5. הזכר מוצרים ומותגים ספציפיים של {site_name} כשרלוונטי

=== פורמט קישורים ===
כל קישור: [טקסט עוגן](https://url-מלא) בלבד.

=== פורמט פלט ===
TITLE: {title}
META_DESCRIPTION: [תיאור מטא]
SLUG: [slug קיים — אל תשנה]

---

[פסקת פתיחה — 2-3 משפטים]

=== תשובה ישירה (לציטוט AI) ===
[40-60 מילים שעונות ישירות על השאילתה הראשית — משפט עצמאי ומלא]

[תוכן מלא בעברית]

---

IMAGE_SUGGESTIONS:
1. [תיאור]
2. [תיאור]
"""


def build_differentiation_prompt(post, winner_post, cluster_query, config):
    """
    Build a prompt to rewrite a cannibalized loser post to target a DIFFERENT
    sub-keyword than the winner, eliminating keyword cannibalization.

    post:          the loser post dict (title, subtitle, body/content_text)
    winner_post:   the winner post dict (title) — the post we must NOT compete with
    cluster_query: the shared query both posts are currently competing for
    config:        site config
    """
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]
    blog_url = config["site"].get("blog_url", f"https://{domain}/blog")

    loser_title = post.get("title", "")
    winner_title = winner_post.get("title", loser_title)
    current_text = post.get("content_text", "") or post.get("subtitle", "")

    return f"""אתה מומחה SEO עבור האתר "{site_name}" ({domain}).

זיהינו בעיית קניבליזציה: שני עמודים מתחרים על אותה שאילתה בגוגל.

=== בעיית הקניבליזציה ===
שאילתה משותפת: "{cluster_query}"
מנצח (אל תתחרה איתו): {winner_title}
מפסיד (העמוד הזה — צריך כיוון שונה): {loser_title}

=== משימה ===
שכתב את העמוד המפסיד כך שיתמקד במשתמש-עניין שונה ומשלים — לא מתחרה — עם המנצח.

למשל:
- אם המנצח מכסה "קורס מנהל עבודה" → כוון ל"קורס מנהל עבודה למהנדסים" / "קורס מנהל עבודה ירושלים"
- אם המנצח מכסה "מזון לכלב בוגר" → כוון ל"מזון לכלב בוגר גזע קטן" / "מזון לכלב בוגר עם בעיות עיכול"

=== התוכן הנוכחי של העמוד (לצורך הבנת ההקשר) ===
{current_text[:2000] if current_text else "לא זמין"}

=== דרישות ===
1. בחר מילת מפתח חדשה ספציפית יותר (long-tail) שלא מתחרה ב: "{winner_title}"
2. כתוב את כל העמוד מחדש סביב מילת המפתח החדשה
3. אורך: לפחות 1500 מילים
4. בלוק תשובה ישירה (AI Overview): מיד לאחר פסקת הפתיחה, כלול:
   === תשובה ישירה (לציטוט AI) ===
   [תשובה ישירה לשאילתה הראשית — בדיוק 40-60 מילים בעברית]
   חובה: בדיוק 40-60 מילים, משפט שלם ועצמאי, ללא הקדמה. מיועד לציטוט על ידי AI Overviews בגוגל.
5. כלול FAQ עם כותרות H2/H3 וקישורים פנימיים. כל תשובת FAQ: בדיוק 2-3 משפטים (40-60 מילים) — תשובה עצמאית ומלאה, מיועדת לחילוץ על ידי AI Overviews.
6. שמור על הכותרת כקו-מנחה אך שנה אותה להתאמה למילת המפתח החדשה
7. שפה: עברית

=== פורמט פלט ===
TITLE: [כותרת חדשה ממוקדת]
META_DESCRIPTION: [150-160 תווים]
SLUG: [slug-חדש-בעברית]
NEW_KEYWORD: [מילת המפתח החדשה שבחרת]

---

[פסקת פתיחה — 2-3 משפטים]

=== תשובה ישירה (לציטוט AI) ===
[40-60 מילים שעונות ישירות על השאילתה הראשית — משפט עצמאי ומלא]

[תוכן מלא בעברית עם markdown]

---
"""


NO_TEXT_INSTRUCTION = (
    "ABSOLUTE RULE — NO TEXT WHATSOEVER: "
    "Zero letters, zero numbers, zero words, zero characters, zero writing of any kind "
    "in ANY language (including Hebrew, English, Arabic, symbols, logos, signs, labels, "
    "watermarks, overlays, captions, subtitles). "
    "If any text appears in the image it is a failure. "
    "Pure photographic scene only — no graphics, no typography, no UI elements."
)


def build_image_prompt(topic, config=None, site_context=None):
    """Build a prompt for Gemini Imagen to generate a square blog post image (1:1).

    One image is generated and used for both desktop and mobile.
    The topic must already be translated to a visual English concept before calling this.
    """
    site_name = ""
    if config:
        site_name = config["site"].get("name", "")

    # NO_TEXT must come first — Imagen weighs early constraints more heavily
    no_text_prefix = (
        "NO TEXT IN IMAGE. No words, no letters, no numbers, no signs, no logos, "
        "no watermarks, no captions in any language. Pure photo only. "
    )

    # Use project-specific image_style from config if available
    image_style = config.get("context", {}).get("image_style", {}) if config else {}

    if image_style:
        description = image_style.get("description", "")
        visual_elements = image_style.get("visual_elements", "")
        color_palette = image_style.get("color_palette", "")

        return (
            f"{no_text_prefix}"
            f"Professional square blog post photo. "
            f"{description} "
            f"Topic shown visually: {topic}. "
            f"Style: high quality stock photography, real people or objects, no graphics. "
            f"{visual_elements} "
            f"Bright, natural lighting. Square 1:1 format. "
            f"{color_palette} "
            f"{NO_TEXT_INSTRUCTION}"
        )

    # Fallback: build from brand_voice in config context
    brand_voice = config.get("context", {}).get("brand_voice", "") if config else ""
    biz_desc = brand_voice.split("\n")[0].strip() if brand_voice else ""

    return (
        f"{no_text_prefix}"
        f"Professional square blog post photo. "
        f"{biz_desc} "
        f"Topic shown visually: {topic}. "
        f"Style: high quality stock photography, real scene, no graphics or illustrations. "
        f"Bright, natural lighting. Square 1:1 format. "
        f"{NO_TEXT_INSTRUCTION}"
    )
