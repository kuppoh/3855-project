/* UPDATE THESE VALUES TO MATCH YOUR SETUP */

const PROCESSING_STATS_API_URL = "http://20.246.105.173:8100/stats"
const ANALYZER_API_URL = {
    stats: "http://20.246.105.173:8200/stats",
    listings: "http://20.246.105.173:8200/site/listings?index=1", 
    bids: "http://20.246.105.173:8200/site/bids?index=1"          
};
// This function fetches and updates the general statistics
const makeReq = (url, cb) => {
    fetch(url)
        .then(res => res.json())
        .then((result) => {
            console.log("Received data: ", result)
            cb(result);
        }).catch((error) => {
            updateErrorMessages(error.message)
        })
}

const getIndex = () => document.getElementById("index").value || 0; // Default to 0 if no input

const updateCodeDiv = (result, elemId) => document.getElementById(elemId).innerText = JSON.stringify(result)

const getLocaleDateStr = () => (new Date()).toLocaleString()

// const getStats = () => {
//     document.getElementById("last-updated-value").innerText = getLocaleDateStr()
    
//     makeReq(PROCESSING_STATS_API_URL, (result) => updateCodeDiv(result, "processing-stats"))
//     makeReq(ANALYZER_API_URL.stats, (result) => updateCodeDiv(result, "analyzer-stats"))
//     makeReq(ANALYZER_API_URL.listings, (result) => updateCodeDiv(result, "event-listings"))
//     makeReq(ANALYZER_API_URL.bids, (result) => updateCodeDiv(result, "event-bids"))
// }

const getStats = () => {
    const index = getIndex(); 
    document.getElementById("last-updated-value").innerText = getLocaleDateStr();

    makeReq(PROCESSING_STATS_API_URL, (result) => updateCodeDiv(result, "processing-stats"));
    makeReq(ANALYZER_API_URL.stats, (result) => updateCodeDiv(result, "analyzer-stats"));
    makeReq(`${ANALYZER_API_URL.listings.split('?')[0]}?index=${index}`, (result) => updateCodeDiv(result, "event-listings"));
    makeReq(`${ANALYZER_API_URL.bids.split('?')[0]}?index=${index}`, (result) => updateCodeDiv(result, "event-bids"));
};

const updateErrorMessages = (message) => {
    const id = Date.now()
    console.log("Creation", id)
    msg = document.createElement("div")
    msg.id = `error-${id}`
    msg.innerHTML = `<p>Something happened at ${getLocaleDateStr()}!</p><code>${message}</code>`
    document.getElementById("messages").style.display = "block"
    document.getElementById("messages").prepend(msg)
    setTimeout(() => {
        const elem = document.getElementById(`error-${id}`)
        if (elem) { elem.remove() }
    }, 7000)
}

const setup = () => {
    getStats()
    setInterval(() => getStats(), 4000) // Update every 4 seconds
}

document.addEventListener('DOMContentLoaded', setup)