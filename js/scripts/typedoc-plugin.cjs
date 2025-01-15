const {
  Application,
  Converter,
  Context,
  ReflectionKind,
  DeclarationReflection,
  RendererEvent,
} = require("typedoc");
const fs = require("fs");
const path = require("path");

// Reflection types to check for methods that should not be documented.
// e.g methods prefixed with `_` or `lc_`
const REFLECTION_KINDS_TO_HIDE = [
  ReflectionKind.Property,
  ReflectionKind.Accessor,
  ReflectionKind.Variable,
  ReflectionKind.Method,
  ReflectionKind.Function,
  ReflectionKind.Class,
  ReflectionKind.Interface,
  ReflectionKind.Enum,
  ReflectionKind.TypeAlias,
];

const BASE_OUTPUT_DIR = "./api_refs";

// Script to inject into the HTML to add a CMD/CTRL + K 'hotkey' which focuses
// on the search input element.
const SCRIPT_HTML = `<script>
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.keyCode === 75) { // Check for CMD + K or CTRL + K
      const input = document.getElementById('tsd-search-field'); // Get the search input element by ID
      input.focus(); // Focus on the search input element
      document.getElementById('tsd-search').style.display = 'block'; // Show the div wrapper with ID tsd-search
    }
  }, false); // Add event listener for keydown events
</script>`;

/**
 * HTML injected into sections where there is a `@deprecated` JSDoc tag.
 * This provides a far more visible warning to the user that the feature is
 * deprecated.
 *
 * @param {string | undefined} deprecationText
 * @returns {string}
 */
const DEPRECATION_HTML = (deprecationText) => `<div class="deprecation-warning">
<h2>⚠️ Deprecated ⚠️</h2>
${deprecationText ? `<p>${deprecationText}</p>` : ""}
<p>This feature is deprecated and will be removed in the future.</p>
<p>It is not recommended for use.</p>
</div>`;

/**
 * Takes in a reflection and an array of all chat model class names.
 * Then performs checks to see if the given reflection should be removed
 * from the documentation.
 * E.g a class method on chat models which is
 * not intended to be documented.
 *
 * @param {DeclarationReflection} reflection
 * @returns {boolean} Whether or not the reflection should be removed
 */
function shouldRemoveReflection(reflection) {
  const kind = reflection.kind;

  if (
    reflection.parent &&
    reflection.name !== "constructor"
  ) {
    if (kind === ReflectionKind.Property) {
      return true;
    }
  }

  if (REFLECTION_KINDS_TO_HIDE.find((kindToHide) => kindToHide === kind)) {
    if (reflection.name.startsWith("_") || reflection.name.startsWith("lc_")) {
      // Remove all reflections which start with an `_` or `lc_`
      return true;
    }
  }
}

/**
 * @param {Application} application
 * @returns {void}
 */
function load(application) {
  application.converter.on(
    Converter.EVENT_CREATE_DECLARATION,
    resolveReflection
  );

  application.renderer.on(RendererEvent.END, onEndRenderEvent);

  /**
   * @param {Context} context
   * @param {DeclarationReflection} reflection
   * @returns {void}
   */
  function resolveReflection(context, reflection) {
    const { project } = context;

    if (shouldRemoveReflection(reflection)) {
      project.removeReflection(reflection);
    }
  }

  /**
   * @param {Context} context
   */
  function onEndRenderEvent(context) {
    const htmlToSplitAtSearchScript = `<div class="tsd-toolbar-contents container">`;
    const htmlToSplitAtVersionDropdown = `<div id="tsd-toolbar-links">`;
    const deprecatedHTML = "<h4>Deprecated</h4>";

    const { urls } = context;
    for (const { url } of urls) {
      const indexFilePath = path.join(BASE_OUTPUT_DIR, url);
      let htmlFileContent = fs.readFileSync(indexFilePath, "utf-8");

      if (htmlFileContent.includes(deprecatedHTML)) {
        // If any comments are added to the `@deprecated` JSDoc, they'll
        // be inside the following <p> tag.
        const deprecationTextRegex = new RegExp(
          `${deprecatedHTML}<p>(.*?)</p>`
        );
        const deprecationTextMatch =
          htmlFileContent.match(deprecationTextRegex);

        /** @type {string | undefined} */
        let textInsidePTag;

        if (deprecationTextMatch) {
          textInsidePTag = deprecationTextMatch[1];
          const newTextToReplace = `${deprecatedHTML}<p>${textInsidePTag}</p>`;
          htmlFileContent = htmlFileContent.replace(
            newTextToReplace,
            DEPRECATION_HTML(textInsidePTag)
          );
        } else {
          htmlFileContent = htmlFileContent.replace(
            deprecatedHTML,
            DEPRECATION_HTML(undefined)
          );
        }
      }

      const [part1, part2] = htmlFileContent.split(htmlToSplitAtSearchScript);
      const htmlWithScript = part1 + SCRIPT_HTML + part2;
      fs.writeFileSync(indexFilePath, htmlWithScript);
    }
  }
}

module.exports = { load };
