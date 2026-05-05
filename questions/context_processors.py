def search_query(request):
    """
    Always expose a safe string for the global search field in base.html.
    Avoids template lookups like request.GET.q (raises if key missing).
    """
    return {"search_query": request.GET.get("q", "").strip()}
