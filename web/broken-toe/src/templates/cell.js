window.addEventListener('load', function() {
    const cell = document.getElementById('cell_{{i}}');
    const i = {{i}};
    const listener{{i}} = () => {
        let state = JSON.parse(atob(document.cookie.split(';')[0].split('=')[1].split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
        if (!state.board[{{i}}]) {
            fetch('{{scheme}}://{{host}}/X/{{id}}',
                {method: 'POST'}
            ).then((resp) => {
                resp.json().then((j) => {
                    let state = JSON.parse(atob(document.cookie.split(';')[0].split('=')[1].split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
                    for (let k in state.board) {
                        if (state.board[k]) {
                            try {
                                document.getElementById(`cell_${k}`).innerText = state.board[k];
                            }
                            catch {}
                        }
                    }
                    if (j.flag) {
                        setTimeout(()=>{
                            alert(j.flag);
                            window.location.reload()
                        }, 100);
                    } else if (j.result) {
                        setTimeout(()=>{
                            alert(j.result)
                            window.location.reload()
                        }, 100);
                    } else {
                        console.log(j);
                    }
                    cell.removeEventListener('click', listener{{i}});
                    cell.addEventListener('click', () => console.log('bad move'));
                });
            })
        }
    }
    cell.addEventListener('click', listener{{i}});
})
