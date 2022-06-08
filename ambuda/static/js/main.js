(function() {

const $ = document.querySelector.bind(document);
const $$ = document.querySelectorAll.bind(document);

function getJSON(url, callback) {
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
    const form = $('#mw-ajax');
    const query = form.querySelector('input[name=q]').value;
    const version = form.querySelector('select[name=version]').value;
    console.log(version);
    const url = `/api/dict/${version}/${query}`;
    getJSON(url, function(resp) {
		if (resp.entries && resp.entries.length > 0) {
			$('#mw-response').innerHTML = '<ul>' + resp.entries.join('') + '</ul>';
		} else {
			$('#mw-response').innerHTML = '<p>No results found.</p>';
		}
    });
}

function toggleSidebar(e) {
    e.preventDefault();
    const classes = $('#sidebar').classList;
    classes.toggle('md:block');
    classes.toggle('md:hidden');
}

$('#mw-ajax').addEventListener('submit', ajaxDict);
$('#toggle-sidebar').addEventListener('click', toggleSidebar);

}());
