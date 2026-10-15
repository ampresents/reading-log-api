import httpx
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("bibliography")


@mcp.tool()
def lookup_book(isbn: str) -> dict:
    """ISBNから書誌情報(書名・著者・出版社)を取得する。本を登録する前に使う。"""
    r = httpx.get("https://api.openbd.jp/v1/get", params={"isbn": isbn}, timeout=10)
    r.raise_for_status()
    data = r.json()
    if not data or data[0] is None:
        return {"error": "書誌情報が見つかりません", "isbn": isbn}
    s = data[0]["summary"]
    return {
        "isbn": isbn,
        "title": s.get("title"),
        "author": s.get("author"),
        "publisher": s.get("publisher"),
    }


if __name__ == "__main__":
    mcp.run()
