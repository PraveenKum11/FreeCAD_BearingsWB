# Wiki source

These pages are the [GitHub wiki](../../wiki) of the Bearings workbench. Edit them here,
in pull requests like the code; on every push to `main`, the `Publish wiki` workflow
(`.github/workflows/wiki.yml`) copies them, with the repository's `images/` folder, to
the wiki.

- One Markdown file per wiki page; the file name is the page name (`Getting-started.md` is
  "Getting started"). Link pages with `[[Page name]]` or `[text](Page-name)`.
- `_Sidebar.md` and `_Footer.md` appear on every page.
- Images: `images/…` (here a link to `../images`, in the wiki a copy of it). Render new
  ones with `tools/render_images.py`.
- `freecad-wiki.txt` is a draft of the page for wiki.freecad.org (MediaWiki markup).

The first time, enable the wiki (Settings → General → Features → Wikis) and create any
first page in the browser; the workflow can only push to a wiki that exists.
