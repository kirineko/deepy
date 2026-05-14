## WebFetch

Fetch a specific web page when the user provides a complete URL.

Args: `url`.

Accepts only complete `http://` or `https://` URLs. Returns the final URL, title,
content type, and extracted readable text for HTML pages, including standard
description metadata when ordinary body text is unavailable. Use `WebSearch` to
discover URLs; use `WebFetch` when the URL is already known.
