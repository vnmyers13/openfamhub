from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("", response_class=HTMLResponse)
async def wall_display():
    return HTMLResponse(
        content="""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, height=1080">
    <title>Family Hub</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: #eee;
            width: 1920px;
            height: 1080px;
            overflow: hidden;
        }
        #app { width: 100%; height: 100%; }
    </style>
</head>
<body>
    <div id="app"></div>
    <script type="module" src="/wall/main.tsx"></script>
</body>
</html>"""
    )
