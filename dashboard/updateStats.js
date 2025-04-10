/* UPDATE THESE VALUES TO MATCH YOUR SETUP */

const PROCESSING_STATS_API_URL = "http://20.246.105.173/processing/stats"
const ANALYZER_API_URL = {
    stats: "http://20.246.105.173/analyzer/stats",
    listings: "http://20.246.105.173/analyzer/site/listings?index=1", 
    bids: "http://20.246.105.173/analyzer/site/bids?index=1"          
};
const CONSISTENCY_API_URL = {
    update: "http://20.246.105.173/consistency_check/update",
    checks: "http://20.246.105.173/consistency_check/checks"
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

// This function performs a POST request to run a consistency check
const runConsistencyCheck = (url, cb) => {
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(res => res.json())
        .then((result) => {
            console.log("Received consistency check result: ", result)
            cb(result);
        }).catch((error) => {
            updateErrorMessages(error.message)
        })
}

const getIndex = () => document.getElementById("index").value || 1; // Default to 1 if no input

const updateCodeDiv = (result, elemId) => document.getElementById(elemId).innerText = JSON.stringify(result, null, 2)

const getLocaleDateStr = () => (new Date()).toLocaleString()

const getStats = () => {
    const index = getIndex(); 
    document.getElementById("last-updated-value").innerText = getLocaleDateStr();

    makeReq(PROCESSING_STATS_API_URL, (result) => updateCodeDiv(result, "processing-stats"));
    makeReq(ANALYZER_API_URL.stats, (result) => updateCodeDiv(result, "analyzer-stats"));
    makeReq(`${ANALYZER_API_URL.listings.split('?')[0]}?index=${index}`, (result) => updateCodeDiv(result, "event-listings"));
    makeReq(`${ANALYZER_API_URL.bids.split('?')[0]}?index=${index}`, (result) => updateCodeDiv(result, "event-bids"));
    
    // Get consistency check results if available
    makeReq(CONSISTENCY_API_URL.checks, (result) => {
        if (result.message) {
            // Handle error or no data case
            document.getElementById("consistency-results").innerText = result.message;
            document.getElementById("missing-db").innerText = "None";
            document.getElementById("missing-queue").innerText = "None";
        } else {
            updateCodeDiv(result.counts, "consistency-results");
            updateCodeDiv(result.missing_in_db, "missing-db");
            updateCodeDiv(result.missing_in_queue, "missing-queue");
        }
    });
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
    
    // Add event listener for consistency check form
    document.getElementById("consistency-form").addEventListener("submit", (e) => {
        e.preventDefault();
        document.getElementById("run-check").disabled = true;
        document.getElementById("run-check").textContent = "Running Check...";
        
        runConsistencyCheck(CONSISTENCY_API_URL.update, (result) => {
            if (result.processing_time_ms) {
                const message = document.createElement("div");
                message.className = "success-message";
                message.textContent = `Consistency check completed in ${result.processing_time_ms}ms`;
                document.getElementById("messages").style.display = "block";
                document.getElementById("messages").prepend(message);
                
                // Get the updated check results
                makeReq(CONSISTENCY_API_URL.checks, (result) => {
                    updateCodeDiv(result.counts, "consistency-results");
                    updateCodeDiv(result.missing_in_db, "missing-db");
                    updateCodeDiv(result.missing_in_queue, "missing-queue");
                });
                
                setTimeout(() => {
                    document.getElementById("run-check").disabled = false;
                    document.getElementById("run-check").textContent = "Run Consistency Check";
                    if (message) { message.remove(); }
                }, 3000);
            } else {
                updateErrorMessages("Error running consistency check");
                document.getElementById("run-check").disabled = false;
                document.getElementById("run-check").textContent = "Run Consistency Check";
            }
        });
    });
}


document.addEventListener('DOMContentLoaded', setup)


