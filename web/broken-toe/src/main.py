import itertools
import logging
import os
import random
import secrets
from typing import Annotated

from fastapi import FastAPI, Path, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import jwt


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__file__)

app = FastAPI(openapi_url=None)
app.mount("/assets", StaticFiles(directory="assets"), name="assets")

jwt_secret = bytes.fromhex(os.getenv("JWT_SECRET_KEY", "abcd1234"*8))
templates = Jinja2Templates(directory="templates")


PLAYER_WINS="X"
SERVER_WINS="O"
NOBODY_WINS="-"
CONTINUE=">"


def assign_nonce(src, real_nonce, fake_nonce):
    nonce = real_nonce if random.choice((True, False)) else fake_nonce
    return {
            "nonce": nonce,
            "src": src
            }


def check_board(board):
    rows = [[itm for itm in slice] for slice in itertools.batched(board.values(), n=3)]
    logger.info(f"check_board: {str(rows)}")

    def is_x(c): return c == "X"
    
    for r in rows:
        if r.count("X") == 3: return PLAYER_WINS

    for i in (0, 1, 2):
        c = [r[i] for r in rows if len(r) > i]
        if c.count("X") == 3: return PLAYER_WINS

    if all(map(is_x, [rows[i][i] for i in (0, 1, 2)])): return PLAYER_WINS

    if all(map(is_x, [rows[i][j] for i,j in zip((0, 1, 2), (2, 1, 0))])): return PLAYER_WINS

    if all(board.values()): return NOBODY_WINS

    return CONTINUE


def complete_3(board: list[list[str|None]], search: str, place: str):
    """
    find 2 of `search` along a tic-tac-toe axis with an empty
    slot, and fill the slot with `place`, mutating `board`

    return True if successful; False if no such move is possible
    """
    for i in (0, 1, 2):
        for j in (0, 1, 2):
            if board[i].count(search) == 2 and None in board[i]:
                board[i][board[i].index(None)] = place
                return True

        col = [board[j][i] for j in (0, 1, 2)]
        if col.count(search) == 2 and None in col:
            board[col.index(None)][i] = place
            return True

    lr = [board[i][i] for i in (0, 1, 2)]
    if lr.count(search) == 2 and None in lr:
        board[lr.index(None)][lr.index(None)] = place
        return True

    rdiag = ((0, 2), (1, 1), (2, 0))
    rl = [board[i][j] for i, j in rdiag]
    if lr.count(search) == 2 and None in lr:
        pos = rdiag[rl.index(None)]
        board[pos[0]][pos[1]] = place
        return True

    return False


def is_two(board, ax, marker):
    vals = [board[m][n] for m, n in ax]
    if vals.count(marker) == 2 and None in vals:
        return True

    return False


def two_open(board, ax):
    vals = [board[m][n] for m, n in ax]
    if vals.count(None) == 2:
        return True

    return False


def make_fork(board: list[list[str|None]], marker: str):
    """
    Create two non-blocked lines of 2, mutating board.
    Return True if the move was made, False if the move is impossible.
    """
    for i, j in itertools.permutations((0, 1, 2), r=2):
        if board[i][j] == marker:
            axes = {}
            axes["row"] = ((i, j), (i, (j + 1) % 3), (i, (j + 2) % 3))
            axes["col"] = ((i, j), ((i + 1) % 3, j), ((i + 2) % 3, j))

            if i + j == 2:
                axes["rl"] = ((i, j), ((i + 2) % 3, (j + 1) % 3), ((i + 1) % 3, (j + 2) % 3))

            if i == j:
                axes["lr"] = ((i, j), ((i + 1) % 3, (j + 1) % 3), ((i + 1) % 3, (j + 1) % 3))

            if all(map(lambda ax: not is_two(board, ax, marker), axes.values())):
                continue

            for k, ax in axes.items():
                if two_open(board, ax):
                    for m, n in ax[1:]:
                        if board[m][n] is None:
                            board[m][n] = marker
                            return True

    return False


def play(board_dict):
    board = [[itm for itm in slice] for slice in itertools.batched(board_dict.values(), n=3)]

    def flat(b):
        res = dict()
        for i, itm in enumerate(itertools.chain.from_iterable(b)):
            res[str(i)] = itm

        return res

    # choose server move and detect server win; return (outcome, board)
    # look for a winning move
    if complete_3(board, "O", "O"):
        logger.info(f"play:win:board={board}")
        return (SERVER_WINS, flat(board))

    # no immediate win; block if necessary
    if complete_3(board, "X", "O"):
        logger.info(f"play:block:board={board}")
        return (CONTINUE, flat(board))

    # no need to block
    if make_fork(board, "O"):
        logger.info(f"play:fork:board={board}")
        return (CONTINUE, flat(board))

    # center if possible
    if board[1][1] is None:
        board[1][1] = "O"
        logger.info(f"play:center:board={board}")
        return (CONTINUE, flat(board))

    # opposite corner
    if board[0][0] == "X" and board[2][2] is None:
        board[2][2] = "O"
        logger.info(f"play:corner22:board={board}")
        return (CONTINUE, flat(board))
    if board[2][2] == "X" and board[0][0] is None:
        board[0][0] = "O"
        logger.info(f"play:corner00:board={board}")
        return (CONTINUE, flat(board))
    if board[0][2] == "X" and board[2][0] is None:
        board[2][0] = "O"
        logger.info(f"play:corner20:board={board}")
        return (CONTINUE, flat(board))
    if board[2][0] == "X" and board[0][2] is None:
        board[0][2] = "O"
        logger.info(f"play:corner02:board={board}")
        return (CONTINUE, flat(board))

    # corner
    for i, j in ((0, 0), (0, 2), (2, 2), (2, 0)):
        if board[i][j] is None:
            board[i][j] = "O"
            logger.info(f"play:corner-any:board={board}")
            return (CONTINUE, flat(board))

    # side
    for i, j in ((0, 1), (1, 2), (2, 1), (1, 0)):
        if board[i][j] is None:
            board[i][j] = "O"
            logger.info(f"play:side-any:board={board}")
            return (CONTINUE, flat(board))

    logger.warn("no move for server")
    return (CONTINUE, flat(board))


@app.middleware("http")
async def log_request(request: Request, call_next):
    response = await call_next(request)
    logger.info(f"{request.method} {request.url} {response.status_code}")
    return response


@app.get("/")
async def index(request: Request):
    nonce = secrets.token_urlsafe(nbytes=18)
    fake_nonce = ("A" if nonce[0] != "A" else "B") + nonce[1:]

    scripts = ["/scripts/reset.js"]
    scripts.extend([f"/scripts/cell/{i}/handler.js" for i in range(9)])
    prepare_script = lambda script: assign_nonce(script, nonce, fake_nonce)

    scripts = list(map(prepare_script, scripts))

    response = templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"scripts": scripts},
            headers={"content-security-policy": f"script-src 'nonce-{nonce}'"}
            )
    response.set_cookie(key="gamestate", value=jwt.encode({"board": {i:None for i in range(9)}}, jwt_secret, algorithm="HS256"))
    return response


@app.post("/X/{_id}")
def x(_id: Annotated[str, Path()], request: Request):
    game_jwt = request.cookies.get("gamestate")
    if game_jwt is None:
        return {"error": "game not found"}

    state = jwt.decode(game_jwt, jwt_secret, algorithms=["HS256"])
    board = state.get("board")
    logger.info(board)
    if board is None:
        return {"error": "board not found"}

    cell = int(request.url.hostname.split(".")[0][4:])
    if board.get(cell):
        return {"error": "bad move"}

    board[cell] = "X"

    outcome = check_board(board)
    if outcome == PLAYER_WINS:
        content = {"flag": os.getenv("THE_FLAG", "test{flag}")}
    elif outcome == NOBODY_WINS:
        content = {"result": "draw"}
    else:
        outcome, board = play(board)
        if outcome == SERVER_WINS:
            content = {"result": "you've been defeated by the immortal machine"}
        elif outcome == NOBODY_WINS:
            content = {"result": "draw"}
        else:
            content = {"continue": True}

    new_jwt = jwt.encode({"board": board}, jwt_secret, algorithm="HS256")
    response = JSONResponse(content=content)
    response.set_cookie(key="gamestate", value=new_jwt)
    return response


@app.get("/scripts/reset.js")
def reset_js():
    js = "window.addEventListener('load', ()=>{document.getElementById('reset-button').addEventListener('onclick',()=>{document.cookie='';window.location.reload();})})"
    return PlainTextResponse(content=js, media_type="application/x-javascript")


@app.get("/scripts/cell/{i}/handler.js")
async def cell_js(i: Annotated[int, Path(ge=0, le=8)], request: Request):
    response = templates.TemplateResponse(
            request=request,
            name="cell.js",
            context={"i": i, "id": secrets.token_hex(nbytes=2), "scheme": request.url.scheme, "host": f"cell{i}.{request.url.hostname}"},
            media_type="application/x-javascript",
            )
    return response
