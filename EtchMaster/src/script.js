const statusTableBody = document.getElementById('statusbody');

async function fetchTemperature(element) {
    let content = await fetch("/status.html");

    let html_data = await content.text();

    statusTableBody.innerHTML = html_data;

    // setTimeout(fetchTemperature, 500);
}

fetchTemperature();