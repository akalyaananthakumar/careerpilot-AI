const messages =
    document.getElementById("messages");

const form =
    document.getElementById("chatForm");

const input =
    document.getElementById("messageInput");

const sendBtn =
    document.getElementById("sendBtn");

const typing =
    document.getElementById("typing");

const clearBtn =
    document.getElementById("clearBtn");

const themeBtn =
    document.getElementById("themeBtn");

const charCount =
    document.getElementById("charCount");


let history = [];

let busy = false;


// ======================================
// ESCAPE HTML
// ======================================

function escapeHtml(text) {

    const div =
        document.createElement("div");

    div.textContent = text;

    return div.innerHTML;
}


// ======================================
// FORMAT AI RESPONSE
// ======================================

function formatText(text) {

    let html =
        escapeHtml(text);


    // Bold
    html = html.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );


    // Inline code
    html = html.replace(
        /`([^`]+)`/g,
        "<code>$1</code>"
    );


    const lines =
        html.split("\n");


    let result = "";

    let inList = false;


    for (const line of lines) {

        const trimmed =
            line.trim();


        // Bullet list
        if (
            /^[-*]\s+/.test(trimmed)
        ) {

            if (!inList) {

                result += "<ul>";

                inList = true;
            }

            result +=
                `<li>${
                    trimmed.replace(
                        /^[-*]\s+/,
                        ""
                    )
                }</li>`;

        }

        else {

            if (inList) {

                result += "</ul>";

                inList = false;
            }


            if (
                /^#{1,3}\s+/.test(
                    trimmed
                )
            ) {

                result +=
                    `<p><strong>${
                        trimmed.replace(
                            /^#{1,3}\s+/,
                            ""
                        )
                    }</strong></p>`;

            }

            else if (trimmed) {

                result +=
                    `<p>${trimmed}</p>`;
            }
        }
    }


    if (inList) {

        result += "</ul>";
    }


    return (
        result ||
        "<p>No response.</p>"
    );
}


// ======================================
// SCROLL
// ======================================

function scrollBottom() {

    messages.scrollTop =
        messages.scrollHeight;
}


// ======================================
// REMOVE WELCOME
// ======================================

function removeWelcome() {

    const welcome =
        messages.querySelector(
            ".welcome"
        );

    if (welcome) {

        welcome.remove();
    }
}


// ======================================
// ADD MESSAGE
// ======================================

function addMessage(
    role,
    text
) {

    removeWelcome();


    const wrapper =
        document.createElement(
            "div"
        );

    wrapper.className =
        `message ${role}`;


    const bubble =
        document.createElement(
            "div"
        );

    bubble.className =
        "bubble";


    if (
        role === "assistant"
    ) {

        bubble.innerHTML =
            formatText(text);


        const copyBtn =
            document.createElement(
                "button"
            );

        copyBtn.className =
            "copy-btn";

        copyBtn.textContent =
            "Copy response";


        copyBtn.addEventListener(
            "click",
            async () => {

                try {

                    await navigator.clipboard
                        .writeText(text);

                    copyBtn.textContent =
                        "Copied ✓";


                    setTimeout(
                        () => {

                            copyBtn.textContent =
                                "Copy response";

                        },
                        1500
                    );

                }

                catch {

                    copyBtn.textContent =
                        "Copy unavailable";
                }
            }
        );


        bubble.appendChild(
            copyBtn
        );

    }

    else {

        bubble.textContent =
            text;
    }


    wrapper.appendChild(
        bubble
    );


    messages.appendChild(
        wrapper
    );


    scrollBottom();
}


// ======================================
// BUSY STATE
// ======================================

function setBusy(state) {

    busy = state;

    sendBtn.disabled =
        state;

    typing.hidden =
        !state;
}


// ======================================
// TEXTAREA RESIZE
// ======================================

function resizeInput() {

    input.style.height =
        "auto";

    input.style.height =
        Math.min(
            input.scrollHeight,
            150
        ) + "px";
}


// ======================================
// SEND MESSAGE
// ======================================

async function sendMessage(
    text = input.value.trim()
) {

    if (
        !text ||
        busy
    ) {

        return;
    }


    // User message
    addMessage(
        "user",
        text
    );


    history.push({

        role: "user",

        content: text

    });


    input.value = "";

    charCount.textContent =
        "0 / 6000";

    resizeInput();

    setBusy(true);


    try {

        const response =
            await fetch(
                "/chat",
                {

                    method: "POST",

                    headers: {

                        "Content-Type":
                            "application/json",

                        "Accept":
                            "application/json"

                    },

                    body: JSON.stringify({

                        message: text,

                        history:
                            history.slice(-10)

                    })
                }
            );


        // IMPORTANT:
        // Read text first.
        // This prevents:
        // Unexpected token '<'
        const rawText =
            await response.text();


        let data;


        try {

            data =
                JSON.parse(
                    rawText
                );

        }

        catch (jsonError) {

            console.error(
                "Invalid JSON:",
                rawText
            );


            throw new Error(
                "The server returned an invalid response. " +
                "Check the Flask terminal."
            );
        }


        // Server error
        if (!response.ok) {

            throw new Error(
                data.error ||
                "Server request failed."
            );
        }


        // Missing response
        if (!data.reply) {

            throw new Error(
                "The AI did not return a response."
            );
        }


        // Add AI response
        addMessage(
            "assistant",
            data.reply
        );


        history.push({

            role: "model",

            content: data.reply

        });


    }

    catch (error) {

        console.error(
            "Chat error:",
            error
        );


        addMessage(
            "assistant",
            "Sorry, something went wrong.\n\n" +
            error.message
        );

    }

    finally {

        setBusy(false);

        input.focus();
    }
}


// ======================================
// FORM
// ======================================

form.addEventListener(
    "submit",
    function(event) {

        event.preventDefault();

        sendMessage();
    }
);


// ======================================
// ENTER KEY
// ======================================

input.addEventListener(
    "keydown",
    function(event) {

        if (
            event.key === "Enter" &&
            !event.shiftKey
        ) {

            event.preventDefault();

            form.requestSubmit();
        }
    }
);


// ======================================
// CHARACTER COUNTER
// ======================================

input.addEventListener(
    "input",
    function() {

        charCount.textContent =
            `${input.value.length} / 6000`;

        resizeInput();
    }
);


// ======================================
// QUICK PROMPTS
// ======================================

document
    .querySelectorAll(
        "[data-prompt]"
    )
    .forEach(
        button => {

            button.addEventListener(
                "click",
                function() {

                    sendMessage(
                        button.dataset.prompt
                    );
                }
            );
        }
    );


// ======================================
// CLEAR CHAT
// ======================================

clearBtn.addEventListener(
    "click",
    function() {

        history = [];


        messages.innerHTML = `

            <div class="welcome">

                <div class="welcome-icon">
                    ${window.CHATBOT_CONFIG.emoji}
                </div>

                <h2>
                    Chat cleared
                </h2>

                <p>
                    Ask me anything about
                    ${window.CHATBOT_CONFIG.title}.
                </p>

            </div>
        `;
    }
);


// ======================================
// DARK MODE
// ======================================

themeBtn.addEventListener(
    "click",
    function() {

        document.body.classList.toggle(
            "dark"
        );


        if (
            document.body.classList.contains(
                "dark"
            )
        ) {

            themeBtn.textContent =
                "☀";

        }

        else {

            themeBtn.textContent =
                "☾";
        }
    }
);


// ======================================
// START
// ======================================

input.focus();
