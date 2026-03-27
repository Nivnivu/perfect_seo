import sys
import os
import yaml
from orchestrator import run_new_pipeline, run_update_pipeline, run_static_pipeline, run_full_pipeline, run_images_pipeline, run_recover_pipeline, run_diagnose_pipeline, run_products_pipeline, run_impact_pipeline, run_dedupe_pipeline, run_restore_titles_pipeline

# Fix Hebrew output on Windows console
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def load_config(path="config.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    # Parse --config flag
    config_path = "config.yaml"
    args = sys.argv[1:]
    filtered_args = []
    i = 0
    while i < len(args):
        if args[i] == "--config" and i + 1 < len(args):
            config_path = args[i + 1]
            i += 2
        else:
            filtered_args.append(args[i])
            i += 1

    config = load_config(config_path)
    seed_keywords = config.get("keywords", {}).get("seeds", [
        "מזון לכלבים",
        "מזון לחתולים",
        "אוכל לכלבים מומלץ",
    ])

    mode = filtered_args[0] if filtered_args else None
    site_name = config["site"]["name"]

    if mode == "new":
        run_new_pipeline(seed_keywords, config)
    elif mode == "update":
        run_update_pipeline(seed_keywords, config)
    elif mode == "static":
        run_static_pipeline(config)
    elif mode == "full":
        run_full_pipeline(seed_keywords, config)
    elif mode == "images":
        run_images_pipeline(config)
    elif mode == "recover":
        run_recover_pipeline(config)
    elif mode == "diagnose":
        run_diagnose_pipeline(config)
    elif mode == "products":
        run_products_pipeline(config)
    elif mode == "impact":
        run_impact_pipeline(config)
    elif mode == "dedupe":
        run_dedupe_pipeline(config)
    elif mode == "restore_titles":
        run_restore_titles_pipeline(config)
    else:
        print(f"{site_name} SEO Blog Engine")
        print("=" * 40)
        print()
        print("Usage:")
        print("  python run.py new                                  Create a single new blog post")
        print("  python run.py update                               Fix/rewrite existing posts")
        print("  python run.py static                               Rewrite static pages (home, registration, etc.)")
        print("  python run.py full                                 Full init: new posts + updates + static pages")
        print("  python run.py images                               Generate images for posts missing them")
        print("  python run.py recover                              Restore pages that lost GSC rankings after updates")
        print("  python run.py diagnose                             Deep SEO analysis: indexing, CWV, cannibalization, trends")
        print("  python run.py products                             SEO-optimize product pages: rewrite content + branded images")
        print("  python run.py impact                               Measure GSC impact of recent updates (before vs after)")
        print("  python run.py dedupe                               Fix cannibalization: merge/delete duplicate-topic posts")
        print("  python run.py restore_titles                       Restore original URL slugs for posts whose title was changed")
        print("  python run.py new --config config.pawly.yaml       Use specific config")
        print()
        print(f"Config: {config_path}")
        print(f"Site: {site_name} ({config['site']['domain']})")
        print(f"Seed keywords: {', '.join(seed_keywords)}")


if __name__ == "__main__":
    main()
