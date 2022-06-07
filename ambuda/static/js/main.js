function get_json(url, callback) {
    const req = new XMLHttpRequest();
    req.onreadystatechange = function() {
        if (req.readyState == XMLHttpRequest.DONE) {
            if (req.status == 200) {
                callback(JSON.parse(req.responseText));
            }
        }
    };
    req.open('GET', url);
    req.send();
}

function ajaxDict(e) {
    e.preventDefault();
    const form = document.getElementById('mw-ajax');
    const query = form.querySelector('input[name=q]').value;
    const version = form.querySelector('select[name=version]').value;
    console.log(version);
    const url = `/api/dict/${version}/${query}`;
    get_json(url, function(resp) {
		if (resp.entries && resp.entries.length > 0) {
			document.querySelector('#mw-response').innerHTML = '<ul>' + resp.entries.join('') + '</ul>';
		} else {
			document.querySelector('#mw-response').innerHTML = '<p>No results found.</p>';
		}
    });
}
const form = document.getElementById('mw-ajax');
form.addEventListener('submit', ajaxDict);
