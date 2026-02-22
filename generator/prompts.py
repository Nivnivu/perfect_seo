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

=== דרישות ===
1. כותרת (H1): כלול את מילת המפתח הראשית. הפוך אותה למושכת קליקים.
2. תיאור מטא: 150-160 תווים, כלול מילת מפתח ראשית, קריאה לפעולה.
3. מבנה: השתמש בכותרות H2 ו-H3. כל H2 צריך לכוון למילת מפתח קשורה.
4. ענה על שאלות "אנשים שואלים גם" באופן טבעי בתוך החלקים הרלוונטיים.
5. אורך: כוון ל-{int(avg_words * 1.2)} מילים לפחות.
6. כלול חלק FAQ בסוף עם השאלות הנפוצות.
7. קישורים פנימיים: שלב 3-5 קישורים פנימיים לדפים אמיתיים באתר (מרשימת הדפים שלמעלה). השתמש בטקסט עוגן טבעי.
8. הזכר מוצרים ומותגים ספציפיים של {site_name} כשזה רלוונטי לנושא.
9. טון: מקצועי אבל חם, בקיא בתזונת חיות מחמד. לא מכירתי.
10. שפה: כתוב הכל בעברית.

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

[פוסט בלוג מלא בעברית עם כותרות markdown (## ל-H2, ### ל-H3) וקישורים בפורמט [טקסט](URL)]

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

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context, topic=post_data.get("title", ""))

    return f"""אתה כותב תוכן SEO מומחה עבור האתר "{site_name}" ({domain}).
שכתב והרחב את הפוסט הקיים.

{context_block}

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

=== דרישות ===
1. שמור על הנושא והכיוון המקורי של הפוסט, אבל שכתב אותו מחדש לחלוטין.
2. כותרת (H1): שפר את הכותרת המקורית. כלול מילת מפתח ראשית.
3. תיאור מטא: 150-160 תווים, כלול מילת מפתח ראשית.
4. מבנה: השתמש בכותרות H2 ו-H3. הוסף חלקים חדשים שחסרים.
5. אורך: כוון ל-{target_wc} מילים לפחות.
6. שלב את כל מילות המפתח החסרות באופן טבעי.
7. כלול חלק FAQ בסוף.
8. קישורים פנימיים: שלב 3-5 קישורים פנימיים לדפים אמיתיים באתר.
9. הזכר מוצרים ומותגים ספציפיים של {site_name} כשזה רלוונטי.
10. טון: מקצועי אבל חם, בקיא בתזונת חיות מחמד. לא מכירתי.
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

[פוסט בלוג מלא בעברית עם כותרות markdown (## ל-H2, ### ל-H3) וקישורים בפורמט [טקסט](URL)]

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


def build_static_page_prompt(page_title, page_id, current_text, config, site_context=None):
    """Build the Gemini prompt for rewriting a static page with SEO improvements."""
    site_name = config["site"]["name"]
    domain = config["site"]["domain"]

    context_block = ""
    if site_context:
        context_block = format_context_for_prompt(site_context)

    return f"""אתה כותב תוכן SEO מומחה עבור האתר "{site_name}" ({domain}).
שכתב את תוכן העמוד הסטטי הבא בצורה משופרת, עשירה יותר ומותאמת SEO.

{context_block}

=== פרטי העמוד ===
כותרת נוכחית: {page_title}
מזהה עמוד: {page_id}

=== תוכן נוכחי ===
{current_text}

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


NO_TEXT_INSTRUCTION = (
    "CRITICAL: The image must contain absolutely NO text, NO letters, NO numbers, "
    "NO characters, NO words, NO writing, NO signs, NO labels, NO watermarks in any language. "
    "Pure visual imagery only."
)


def build_image_prompt(topic, title, variant="desktop", config=None, site_context=None):
    """Build a prompt for Gemini Imagen to generate a blog header image.

    The topic should already be translated to English before calling this function.
    """
    if variant == "desktop":
        size_desc = "wide landscape banner (16:9 ratio)"
    else:
        size_desc = "compact portrait image (3:4 ratio)"

    site_name = ""
    if config:
        site_name = config["site"].get("name", "")

    # Use project-specific image_style from config if available
    image_style = config.get("context", {}).get("image_style", {}) if config else {}

    if image_style:
        description = image_style.get("description", "")
        visual_elements = image_style.get("visual_elements", "")
        color_palette = image_style.get("color_palette", "")

        return (
            f"Professional, clean blog header photo for '{site_name}', "
            f"{description} "
            f"The blog post is about: {topic}. "
            f"Style: modern, high quality stock photography. "
            f"{visual_elements} "
            f"Bright, natural lighting. {size_desc}. "
            f"{color_palette} "
            f"{NO_TEXT_INSTRUCTION}"
        )

    # Fallback: build from brand_voice and brands in config context
    brand_desc = ""
    brand_voice = config.get("context", {}).get("brand_voice", "") if config else ""
    if site_context:
        brands = site_context.get("brand_info", {}).get("brands", [])
        if brands:
            brand_names = ", ".join(b["name"] for b in brands[:4])
            brand_desc = f"The company's main areas: {brand_names}. "

    biz_desc = brand_voice.split("\n")[0].strip() if brand_voice else ""

    return (
        f"Professional, clean blog header photo for '{site_name}'. "
        f"{biz_desc} "
        f"{brand_desc}"
        f"The blog post is about: {topic}. "
        f"Style: modern, high quality stock photography. "
        f"Bright, natural lighting. {size_desc}. "
        f"{NO_TEXT_INSTRUCTION}"
    )
