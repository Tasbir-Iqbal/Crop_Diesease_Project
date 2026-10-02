document.addEventListener("DOMContentLoaded", () => {
  /* =====================================================
     VIEW SWITCHING
     ===================================================== */

  const navLinks = document.querySelectorAll("[data-view-link]");
  const views = document.querySelectorAll(".dash-view");

  function switchView(viewName) {
    navLinks.forEach((button) => {
      button.classList.toggle(
        "active",
        button.dataset.viewLink === viewName
      );
    });

    views.forEach((section) => {
      section.classList.toggle(
        "active",
        section.dataset.view === viewName
      );
    });
  }

  navLinks.forEach((button) => {
    button.addEventListener("click", () => {
      switchView(button.dataset.viewLink);
    });
  });


  /* =====================================================
     SCAN VIEW
     ===================================================== */

  const scanFieldSelect =
    document.getElementById("scan-field-select");

  const dropzone =
    document.getElementById("scan-dropzone");

  const fileInput =
    document.getElementById("scan-file-input");

  const preview =
    document.getElementById("scan-preview");

  const previewImg =
    document.getElementById("scan-preview-img");

  const previewName =
    document.getElementById("scan-preview-name");

  const retakeBtn =
    document.getElementById("scan-retake-btn");

  const cropSelect =
    document.getElementById("scan-crop-select");

  const analyzeBtn =
    document.getElementById("scan-analyze-btn");

  const resultEmpty =
    document.getElementById("result-empty");

  const resultLoading =
    document.getElementById("result-loading");

  const resultError =
    document.getElementById("result-error");

  const resultContent =
    document.getElementById("result-content");

  const resultDisease =
    document.getElementById("result-disease");

  const resultLatin =
    document.getElementById("result-latin");

  const resultConfidence =
    document.getElementById("result-confidence");

  const resultCrop =
    document.getElementById("result-crop");

  const resultSpread =
    document.getElementById("result-spread");

  const resultTreatment =
    document.getElementById("result-treatment");

  const resultNote =
    document.getElementById("result-note");

  let selectedFile = null;


  function showResultState(state) {
    [
      resultEmpty,
      resultLoading,
      resultError,
      resultContent
    ].forEach((element) => {
      if (element) {
        element.classList.remove("active");
      }
    });

    const states = {
      empty: resultEmpty,
      loading: resultLoading,
      error: resultError,
      content: resultContent
    };

    if (states[state]) {
      states[state].classList.add("active");
    }
  }


  function showError(message) {
    if (resultError) {
      const errorText =
        resultError.querySelector("p");

      if (errorText) {
        errorText.textContent = message;
      }
    }

    showResultState("error");
  }


  if (dropzone && fileInput) {
    dropzone.addEventListener("click", () => {
      fileInput.click();
    });

    dropzone.addEventListener("dragover", (event) => {
      event.preventDefault();
      dropzone.classList.add("dragover");
    });

    dropzone.addEventListener("dragleave", () => {
      dropzone.classList.remove("dragover");
    });

    dropzone.addEventListener("drop", (event) => {
      event.preventDefault();
      dropzone.classList.remove("dragover");

      if (event.dataTransfer.files.length) {
        handleFile(event.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener("change", () => {
      if (fileInput.files.length) {
        handleFile(fileInput.files[0]);
      }
    });
  }


  function handleFile(file) {
    const allowedTypes = [
      "image/jpeg",
      "image/jpg",
      "image/png",
      "image/webp"
    ];

    if (!allowedTypes.includes(file.type)) {
      alert("Please choose a JPG, PNG or WEBP image.");
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert("Image must be smaller than 10 MB.");
      return;
    }

    selectedFile = file;

    const reader = new FileReader();

    reader.onload = (event) => {
      if (previewImg) {
        previewImg.src = event.target.result;
      }

      if (previewName) {
        previewName.textContent = file.name;
      }

      if (dropzone) {
        dropzone.style.display = "none";
      }

      if (preview) {
        preview.classList.add("active");
      }

      showResultState("empty");
    };

    reader.readAsDataURL(file);
  }


  if (retakeBtn) {
    retakeBtn.addEventListener("click", () => {
      selectedFile = null;

      if (fileInput) {
        fileInput.value = "";
      }

      if (previewImg) {
        previewImg.src = "";
      }

      if (preview) {
        preview.classList.remove("active");
      }

      if (dropzone) {
        dropzone.style.display = "flex";
      }

      showResultState("empty");
    });
  }


  if (analyzeBtn) {
    analyzeBtn.addEventListener(
      "click",
      async () => {
        if (!selectedFile) {
          alert("Choose a leaf photo first.");
          return;
        }

        showResultState("loading");
        analyzeBtn.disabled = true;

        const formData = new FormData();

        formData.append(
          "image",
          selectedFile
        );

        formData.append(
          "crop",
          cropSelect
            ? cropSelect.value
            : ""
        );

        formData.append(
          "field",
          scanFieldSelect
            ? scanFieldSelect.value
            : ""
        );

        try {
          const response = await fetch(
            "/api/analyze",
            {
              method: "POST",
              body: formData,
              credentials: "same-origin"
            }
          );

          let data;

          try {
            data = await response.json();
          } catch {
            throw new Error(
              `Server returned HTTP ${response.status}.`
            );
          }

          if (!response.ok || !data.success) {
            throw new Error(
              data.error ||
              "This image could not be analyzed."
            );
          }

          renderResult(data);
          showResultState("content");
          addHistoryRow(data);

        } catch (error) {
          console.error(
            "Analyze error:",
            error
          );

          showError(
            error.message ||
            "Something went wrong. Please try again."
          );

        } finally {
          analyzeBtn.disabled = false;
        }
      }
    );
  }


  function renderResult(data) {
    if (resultDisease) {
      resultDisease.textContent =
        (data.disease || "")
          .replace(/_/g, " ");
    }

    if (resultLatin) {
      resultLatin.textContent =
        data.latin || "";
    }

    if (resultConfidence) {
      resultConfidence.textContent =
        data.confidence != null
          ? `${data.confidence}% confidence`
          : "—";
    }

    if (resultCrop) {
      resultCrop.textContent =
        data.crop || "—";
    }

    if (resultSpread) {
      resultSpread.textContent =
        data.spread_risk || "—";
    }

    if (resultNote) {
      resultNote.textContent =
        data.note || "";
    }

    if (resultTreatment) {
      resultTreatment.innerHTML = "";

      (data.treatment || []).forEach((step) => {
        const listItem =
          document.createElement("li");

        listItem.textContent = step;

        resultTreatment.appendChild(listItem);
      });
    }

    if (Array.isArray(data.top5)) {
      console.log(
        "Top 5 predictions:",
        data.top5
      );
    }
  }


  /* =====================================================
     HISTORY VIEW
     ===================================================== */

  const historyEmpty =
    document.getElementById("history-empty");

  const historyTable =
    document.getElementById("history-table");

  const historyTableBody =
    document.getElementById("history-table-body");

  const historyFieldFilter =
    document.getElementById("history-field-filter");

  let loadedHistoryScans = [];


  function toggleHistoryEmptyState() {
    if (
      !historyEmpty ||
      !historyTable ||
      !historyTableBody
    ) {
      return;
    }

    const hasRows =
      historyTableBody.children.length > 0;

    historyEmpty.classList.toggle(
      "active",
      !hasRows
    );

    historyTable.style.display =
      hasRows
        ? "table"
        : "none";
  }


  function formatScanDate(value) {
    if (!value) {
      return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleDateString(
      undefined,
      {
        year: "numeric",
        month: "short",
        day: "numeric"
      }
    );
  }


  function buildHistoryRow(scan) {
    const row =
      document.createElement("tr");

    const scanId =
      scan.id || scan.scan_id;

    const diseaseName =
      (scan.disease || "")
        .replace(/_/g, " ");

    const confidence =
      scan.confidence != null
        ? `${scan.confidence}% confidence`
        : "—";

    const field =
      scan.field && scan.field.trim()
        ? scan.field
        : "—";

    const crop =
      scan.crop && scan.crop.trim()
        ? scan.crop
        : "—";

    row.innerHTML = `
      <td>${formatScanDate(scan.created_at)}</td>
      <td>${field}</td>
      <td>${crop}</td>
      <td>${diseaseName || "—"}</td>
      <td>${confidence}</td>
      <td>
        <a
          href="/api/report/${scanId}"
          target="_blank"
          rel="noopener"
        >
          Download PDF
        </a>
      </td>
    `;

    return row;
  }


  function addHistoryRow(data) {
    if (!historyTableBody) {
      return;
    }

    const newScan = {
      id: data.scan_id,
      scan_id: data.scan_id,
      created_at: new Date().toISOString(),
      field: data.field,
      crop: data.crop,
      disease: data.disease,
      confidence: data.confidence
    };

    loadedHistoryScans.unshift(newScan);

    renderFilteredHistory();
  }


  function renderFilteredHistory() {
    if (!historyTableBody) {
      return;
    }

    historyTableBody.innerHTML = "";

    const selectedLocation =
      historyFieldFilter
        ? historyFieldFilter.value
        : "all";

    const scansToDisplay =
      selectedLocation === "all" ||
      selectedLocation === ""
        ? loadedHistoryScans
        : loadedHistoryScans.filter((scan) => {
            return scan.field === selectedLocation;
          });

    scansToDisplay.forEach((scan) => {
      historyTableBody.appendChild(
        buildHistoryRow(scan)
      );
    });

    toggleHistoryEmptyState();
  }


  async function loadHistory() {
    if (!historyTableBody) {
      return;
    }

    try {
      const response = await fetch(
        "/api/history",
        {
          method: "GET",
          credentials: "same-origin"
        }
      );

      const data =
        await response.json();

      if (!response.ok || !data.success) {
        throw new Error(
          data.error ||
          "Could not load history."
        );
      }

      loadedHistoryScans =
        data.history || [];

      renderFilteredHistory();

    } catch (error) {
      console.error(
        "History load error:",
        error
      );
    }
  }


  if (historyFieldFilter) {
    historyFieldFilter.addEventListener(
      "change",
      renderFilteredHistory
    );
  }


  loadHistory();


  const historyNavLink =
    document.querySelector(
      '[data-view-link="history"]'
    );

  if (historyNavLink) {
    historyNavLink.addEventListener(
      "click",
      loadHistory
    );
  }


  /* =====================================================
     CHAT VIEW
     ===================================================== */

  (function () {
    const chatLog =
      document.getElementById("chat-log");

    const chatForm =
      document.getElementById("chat-form");

    const chatTextarea =
      document.getElementById("chat-textarea");

    const attachBtn =
      document.getElementById("chat-attach-btn");

    const attachInput =
      document.getElementById("chat-attach-input");

    const attachChip =
      document.getElementById("chat-attachment-chip");

    const attachName =
      document.getElementById("chat-attachment-name");

    const attachRemove =
      document.getElementById(
        "chat-attachment-remove"
      );

    let attachedDocument = null;

    if (
      !chatLog ||
      !chatForm ||
      !chatTextarea ||
      !attachBtn ||
      !attachInput ||
      !attachChip ||
      !attachName ||
      !attachRemove
    ) {
      return;
    }


    function escapeHtml(value) {
      return value
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }


    function renderMarkdown(markdown) {
      if (!markdown) {
        return "";
      }

      const codeBlocks = [];

      markdown = markdown.replace(
        /```([\s\S]*?)```/g,
        (_, code) => {
          codeBlocks.push(
            code.replace(/^\w*\n/, "")
          );

          return (
            `\u0000CODEBLOCK${
              codeBlocks.length - 1
            }\u0000`
          );
        }
      );

      let html =
        escapeHtml(markdown);

      html = html.replace(
        /`([^`]+)`/g,
        "<code>$1</code>"
      );

      html = html.replace(
        /^###\s?(.*)$/gm,
        "<h3>$1</h3>"
      );

      html = html.replace(
        /^##\s?(.*)$/gm,
        "<h2>$1</h2>"
      );

      html = html.replace(
        /^#\s?(.*)$/gm,
        "<h1>$1</h1>"
      );

      html = html.replace(
        /\*\*(.+?)\*\*/g,
        "<strong>$1</strong>"
      );

      html = html.replace(
        /(?<!\*)\*(?!\*)(.+?)\*(?!\*)/g,
        "<em>$1</em>"
      );

      html = html.replace(
        /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
      );

      html = html.replace(
        /(^|\n)((?:[-*]\s.+\n?)+)/g,
        (match, lead, block) => {
          const items = block
            .trim()
            .split("\n")
            .map((line) => {
              return `<li>${line.replace(
                /^[-*]\s/,
                ""
              )}</li>`;
            })
            .join("");

          return `${lead}<ul>${items}</ul>`;
        }
      );

      html = html.replace(
        /(^|\n)((?:\d+\.\s.+\n?)+)/g,
        (match, lead, block) => {
          const items = block
            .trim()
            .split("\n")
            .map((line) => {
              return `<li>${line.replace(
                /^\d+\.\s/,
                ""
              )}</li>`;
            })
            .join("");

          return `${lead}<ol>${items}</ol>`;
        }
      );

      html = html.replace(
        /^---$/gm,
        "<hr>"
      );

      html = html
        .split(/\n{2,}/)
        .map((block) => {
          const trimmed = block.trim();

          if (!trimmed) {
            return "";
          }

          if (
            /^<(h1|h2|h3|ul|ol|hr|pre)/.test(
              trimmed
            )
          ) {
            return trimmed;
          }

          return `<p>${trimmed.replace(
            /\n/g,
            "<br>"
          )}</p>`;
        })
        .join("");

      return html.replace(
        /\u0000CODEBLOCK(\d+)\u0000/g,
        (_, index) => {
          return `<pre><code>${escapeHtml(
            codeBlocks[Number(index)]
          )}</code></pre>`;
        }
      );
    }


    function addMessage(text, sender) {
      const wrapper =
        document.createElement("div");

      wrapper.className =
        `msg msg-${
          sender === "ai"
            ? "ai"
            : "user"
        }`;

      const label =
        document.createElement("span");

      label.className = "msg-label";

      label.textContent =
        sender === "ai"
          ? "FieldScan AI"
          : "You";

      const bubble =
        document.createElement("div");

      bubble.className = "bubble";

      if (sender === "ai") {
        bubble.innerHTML =
          renderMarkdown(text);
      } else {
        bubble.textContent = text;
      }

      wrapper.appendChild(label);
      wrapper.appendChild(bubble);
      chatLog.appendChild(wrapper);

      chatLog.scrollTop =
        chatLog.scrollHeight;

      return bubble;
    }


    function setAttachmentChip(name) {
      attachName.textContent =
        name || "";

      attachChip.style.display =
        name
          ? "flex"
          : "none";
    }


    function autoResizeTextarea() {
      chatTextarea.style.height =
        "auto";

      chatTextarea.style.height =
        `${chatTextarea.scrollHeight}px`;
    }


    attachBtn.addEventListener(
      "click",
      () => attachInput.click()
    );


    attachInput.addEventListener(
      "change",
      async () => {
        const file =
          attachInput.files[0];

        if (!file) {
          return;
        }

        const formData =
          new FormData();

        formData.append(
          "file",
          file
        );

        addMessage(
          `Uploading "${file.name}"…`,
          "ai"
        );

        const statusBubble =
          chatLog.lastElementChild
            .querySelector(".bubble");

        try {
          const response =
            await fetch(
              "/upload_document",
              {
                method: "POST",
                body: formData,
                credentials: "same-origin"
              }
            );

          const data =
            await response.json();

          if (!response.ok || data.error) {
            statusBubble.textContent =
              `Couldn't read that file: ${
                data.error ||
                "unknown error"
              }`;

            attachedDocument = null;
            setAttachmentChip(null);
            return;
          }

          attachedDocument = {
            name: file.name,
            content: data.content
          };

          setAttachmentChip(
            file.name
          );

          statusBubble.textContent =
            `Got it — I've read "${file.name}". Ask me anything about it.`;

        } catch (error) {
          statusBubble.textContent =
            `Upload failed: ${error.message}`;

          attachedDocument = null;
          setAttachmentChip(null);

        } finally {
          attachInput.value = "";
        }
      }
    );


    attachRemove.addEventListener(
      "click",
      () => {
        attachedDocument = null;
        setAttachmentChip(null);
      }
    );


    async function sendPrompt(userText) {
      if (!userText.trim()) {
        return;
      }

      addMessage(
        userText,
        "user"
      );

      chatTextarea.value = "";
      autoResizeTextarea();

      const thinkingBubble =
        addMessage(
          "Thinking…",
          "ai"
        );

      let finalPrompt =
        userText;

      if (
        attachedDocument &&
        attachedDocument.content
      ) {
        finalPrompt =
          `Here is the content of an uploaded document named "${attachedDocument.name}":\n\n` +
          `${attachedDocument.content}\n\n` +
          `---\n\n` +
          `Based on that document, answer this question:\n` +
          userText;
      }

      try {
        const response =
          await fetch(
            "/generate",
            {
              method: "POST",
              headers: {
                "Content-Type":
                  "application/json"
              },
              credentials:
                "same-origin",
              body: JSON.stringify({
                prompt: finalPrompt
              })
            }
          );

        const data =
          await response.json();

        if (!response.ok || data.error) {
          thinkingBubble.innerHTML =
            renderMarkdown(
              `Error: ${
                data.error ||
                "Something went wrong."
              }`
            );

          return;
        }

        thinkingBubble.innerHTML =
          renderMarkdown(
            data.response ||
            "(no response)"
          );

      } catch (error) {
        thinkingBubble.innerHTML =
          renderMarkdown(
            `Request failed: ${error.message}`
          );
      }
    }


    chatForm.addEventListener(
      "submit",
      (event) => {
        event.preventDefault();
        sendPrompt(
          chatTextarea.value
        );
      }
    );


    chatTextarea.addEventListener(
      "input",
      autoResizeTextarea
    );


    chatTextarea.addEventListener(
      "keydown",
      (event) => {
        if (
          event.key === "Enter" &&
          !event.shiftKey
        ) {
          event.preventDefault();
          chatForm.requestSubmit();
        }
      }
    );


    document
      .querySelectorAll(".suggested-q")
      .forEach((button) => {
        button.addEventListener(
          "click",
          () => sendPrompt(
            button.textContent
          )
        );
      });


    setAttachmentChip(null);
  })();


  /* =====================================================
     SETTINGS VIEW
     ===================================================== */

  const settingsSaveBtn =
    document.getElementById(
      "settings-save-btn"
    );

  const settingsSaveStatus =
    document.getElementById(
      "settings-save-status"
    );

  const settingsName =
    document.getElementById(
      "settings-name"
    );

  const settingsEmail =
    document.getElementById(
      "settings-email"
    );

  const settingsNotify =
    document.getElementById(
      "settings-notify"
    );

  const settingsUnits =
    document.getElementById(
      "settings-units"
    );

  const settingsDeleteBtn =
    document.getElementById(
      "settings-delete-account-btn"
    );


  if (settingsSaveBtn) {
    settingsSaveBtn.addEventListener(
      "click",
      async () => {
        if (
          !settingsEmail ||
          !settingsEmail.value.includes("@")
        ) {
          if (settingsSaveStatus) {
            settingsSaveStatus.textContent =
              "Enter a valid email.";
          }

          return;
        }

        settingsSaveBtn.disabled = true;

        if (settingsSaveStatus) {
          settingsSaveStatus.textContent =
            "Saving…";
        }

        try {
          const response =
            await fetch(
              "/api/settings",
              {
                method: "POST",
                headers: {
                  "Content-Type":
                    "application/json"
                },
                credentials:
                  "same-origin",
                body: JSON.stringify({
                  name: settingsName
                    ? settingsName.value
                    : "",
                  email: settingsEmail.value,
                  notify: settingsNotify
                    ? settingsNotify.checked
                    : false,
                  metric_units: settingsUnits
                    ? settingsUnits.checked
                    : false
                })
              }
            );

          const data =
            await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.error ||
              "Could not save settings."
            );
          }

          if (settingsSaveStatus) {
            settingsSaveStatus.textContent =
              "Saved.";
          }

        } catch (error) {
          console.error(
            "Settings save error:",
            error
          );

          if (settingsSaveStatus) {
            settingsSaveStatus.textContent =
              error.message ||
              "Couldn't save — try again.";
          }

        } finally {
          settingsSaveBtn.disabled =
            false;

          setTimeout(() => {
            if (settingsSaveStatus) {
              settingsSaveStatus.textContent =
                "";
            }
          }, 3000);
        }
      }
    );
  }


  const settingsPasswordBtn =
    document.getElementById(
      "settings-password-btn"
    );

  const settingsPasswordStatus =
    document.getElementById(
      "settings-password-status"
    );

  const settingsCurrentPassword =
    document.getElementById(
      "settings-current-password"
    );

  const settingsNewPassword =
    document.getElementById(
      "settings-new-password"
    );

  const settingsConfirmPassword =
    document.getElementById(
      "settings-confirm-password"
    );


  if (settingsPasswordBtn) {
    settingsPasswordBtn.addEventListener(
      "click",
      async () => {
        const current =
          settingsCurrentPassword
            ? settingsCurrentPassword.value
            : "";

        const next =
          settingsNewPassword
            ? settingsNewPassword.value
            : "";

        const confirm =
          settingsConfirmPassword
            ? settingsConfirmPassword.value
            : "";

        if (!current || !next || !confirm) {
          settingsPasswordStatus.textContent =
            "Fill in all three fields.";

          return;
        }

        if (next.length < 8) {
          settingsPasswordStatus.textContent =
            "New password must be at least 8 characters.";

          return;
        }

        if (next !== confirm) {
          settingsPasswordStatus.textContent =
            "New passwords don't match.";

          return;
        }

        settingsPasswordBtn.disabled =
          true;

        settingsPasswordStatus.textContent =
          "Updating…";

        try {
          const response =
            await fetch(
              "/api/settings/password",
              {
                method: "POST",
                headers: {
                  "Content-Type":
                    "application/json"
                },
                credentials:
                  "same-origin",
                body: JSON.stringify({
                  current_password: current,
                  new_password: next
                })
              }
            );

          const data =
            await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.error ||
              "Could not update password."
            );
          }

          settingsPasswordStatus.textContent =
            "Password updated.";

          settingsCurrentPassword.value =
            "";

          settingsNewPassword.value =
            "";

          settingsConfirmPassword.value =
            "";

        } catch (error) {
          console.error(
            "Password update error:",
            error
          );

          settingsPasswordStatus.textContent =
            error.message ||
            "Couldn't update — try again.";

        } finally {
          settingsPasswordBtn.disabled =
            false;

          setTimeout(() => {
            settingsPasswordStatus.textContent =
              "";
          }, 4000);
        }
      }
    );
  }


  const settingsCardBtn =
    document.getElementById(
      "settings-card-btn"
    );

  const settingsCardStatus =
    document.getElementById(
      "settings-card-status"
    );

  const settingsCardName =
    document.getElementById(
      "settings-card-name"
    );

  const settingsCardNumber =
    document.getElementById(
      "settings-card-number"
    );

  const settingsCardExpiry =
    document.getElementById(
      "settings-card-expiry"
    );

  const settingsCardCvc =
    document.getElementById(
      "settings-card-cvc"
    );


  if (settingsCardNumber) {
    settingsCardNumber.addEventListener(
      "input",
      () => {
        const digits =
          settingsCardNumber.value
            .replace(/\D/g, "")
            .slice(0, 16);

        settingsCardNumber.value =
          digits
            .replace(
              /(.{4})/g,
              "$1 "
            )
            .trim();
      }
    );
  }


  if (settingsCardExpiry) {
    settingsCardExpiry.addEventListener(
      "input",
      () => {
        const digits =
          settingsCardExpiry.value
            .replace(/\D/g, "")
            .slice(0, 4);

        settingsCardExpiry.value =
          digits.length > 2
            ? `${digits.slice(0, 2)}/${digits.slice(2)}`
            : digits;
      }
    );
  }


  if (settingsCardCvc) {
    settingsCardCvc.addEventListener(
      "input",
      () => {
        settingsCardCvc.value =
          settingsCardCvc.value
            .replace(/\D/g, "")
            .slice(0, 4);
      }
    );
  }


  function isValidExpiry(value) {
    const match =
      /^(\d{2})\/(\d{2})$/.exec(
        value
      );

    if (!match) {
      return false;
    }

    const month =
      parseInt(match[1], 10);

    return month >= 1 && month <= 12;
  }


  if (settingsCardBtn) {
    settingsCardBtn.addEventListener(
      "click",
      async () => {
        const cardDigits =
          settingsCardNumber.value
            .replace(/\s/g, "");

        if (!settingsCardName.value.trim()) {
          settingsCardStatus.textContent =
            "Enter the name on the card.";

          return;
        }

        if (
          cardDigits.length < 13 ||
          cardDigits.length > 16
        ) {
          settingsCardStatus.textContent =
            "Enter a valid card number.";

          return;
        }

        if (
          !isValidExpiry(
            settingsCardExpiry.value
          )
        ) {
          settingsCardStatus.textContent =
            "Enter expiry as MM/YY.";

          return;
        }

        if (
          settingsCardCvc.value.length < 3
        ) {
          settingsCardStatus.textContent =
            "Enter a valid CVC.";

          return;
        }

        settingsCardBtn.disabled =
          true;

        settingsCardStatus.textContent =
          "Saving…";

        try {
          const response =
            await fetch(
              "/api/settings/billing",
              {
                method: "POST",
                headers: {
                  "Content-Type":
                    "application/json"
                },
                credentials:
                  "same-origin",
                body: JSON.stringify({
                  card_name:
                    settingsCardName.value,
                  card_number:
                    cardDigits,
                  expiry:
                    settingsCardExpiry.value,
                  cvc:
                    settingsCardCvc.value
                })
              }
            );

          const data =
            await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.error ||
              "Could not save card."
            );
          }

          settingsCardStatus.textContent =
            "Card saved.";

          settingsCardNumber.value =
            data.last4
              ? `•••• •••• •••• ${data.last4}`
              : "";

          settingsCardCvc.value =
            "";

        } catch (error) {
          console.error(
            "Billing save error:",
            error
          );

          settingsCardStatus.textContent =
            error.message ||
            "Couldn't save card — try again.";

        } finally {
          settingsCardBtn.disabled =
            false;

          setTimeout(() => {
            settingsCardStatus.textContent =
              "";
          }, 4000);
        }
      }
    );
  }


  if (settingsDeleteBtn) {
    settingsDeleteBtn.addEventListener(
      "click",
      async () => {
        const confirmed =
          confirm(
            "Delete your account? This removes your scan history and cannot be undone."
          );

        if (!confirmed) {
          return;
        }

        settingsDeleteBtn.disabled =
          true;

        try {
          const response =
            await fetch(
              "/api/account",
              {
                method: "DELETE",
                credentials:
                  "same-origin"
              }
            );

          const data =
            await response.json();

          if (!response.ok || !data.success) {
            throw new Error(
              data.error ||
              "Could not delete account."
            );
          }

          window.location.href =
            "/logout";

        } catch (error) {
          console.error(
            "Delete account error:",
            error
          );

          alert(
            "Something went wrong deleting your account. Please try again."
          );

          settingsDeleteBtn.disabled =
            false;
        }
      }
    );
  }
});