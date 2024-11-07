document.addEventListener("DOMContentLoaded", function () {
    const englishText = document.querySelector(".vertical-text.english");

    function addLineSpacing(element) {
        const words = element.textContent.split(" ");
        element.innerHTML = ""; // Clear existing content

        let previousTop = null;
        var lineNo = 0;

        // Loop through each word and add it as a span
        words.forEach((word, index) => {
            const wordSpan = document.createElement("span");
            wordSpan.textContent = word + (index < words.length - 1 ? " " : ""); // Add space after each word except the last
            element.appendChild(wordSpan);

            // Measure word position
            const rect = wordSpan.getBoundingClientRect();
            const currentTop = rect.left;

            if (previousTop !== null && currentTop > previousTop) {
                // If word is on a new line, add spacing
                if (lineNo % 3 == 1) {
                    wordSpan.style.marginTop = "0.2em";
                }
                if (lineNo % 3 == 2) {
                    wordSpan.style.marginTop = "0.1em";
                }
                lineNo++;
            }

            previousTop = currentTop;
        });
    }

    addLineSpacing(englishText);
});
