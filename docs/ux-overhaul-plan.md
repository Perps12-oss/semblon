# Semblon GUI overhaul — Safelight Desk

**Status:** design plan for the production shell (`semblon shell`).  
**One GUI:** PySide6 `Shell.qml` remains the only product interface. This pass replaces the launchpad, chrome, and the words people read. It does not add a second app.

## What a person can do

These are the actions the archive already performs. The interface names them in ordinary language.

| Person does | Where |
|---|---|
| Add a folder of pictures. The files stay where they are. | Home, sidebar, first-run |
| See that an add is working, pause it, resume it, or stop it | Task sheet |
| Look through pictures by year, month, and day | Library |
| Open one day, a folder, a moment, everything, or pictures with no date | Library |
| Open a picture, move through neighbours, zoom | Picture view |
| Point or draw, then find other pictures with that look | Picture view |
| Find the same face, the whole picture, words in pictures, or recognised things | Picture view and search |
| Ask about the open picture | Picture view |
| Save a find and open it again | Picture view, Home |
| Look at the screen and match what is there | Picture view, when that extra piece is ready |
| Review suggested groups and name someone only when sure | People |
| Merge, split, leave unknown, note, or mark “not the same person” | People |
| See the days a named person appears, then browse that time | People |
| Look for copies | Settings, and the picture view |
| Change the colour theme, photo size, and how hard a search looks | Settings |
| See what is ready on this computer and install a missing extra | Settings |
| Check the library, look through a folder again, clear the index | Settings |
| Read recent activity | Settings / activity sheet |

A group is not a person until the person types a name. Unknown stays valid. A missing extra, a missing file, and a genuine empty match stay different sentences.

## Information architecture

One window. A slim spine on the left. One stage.

```text
Spine          Stage (only one of these fills it)
Home           First arrival, or a return desk
Library        Calendar, then a day or a selection, then one picture
People         Groups to look at, then one group
Add folder     Starts an add. Does not leave the stage.
Settings       A sheet over the stage, not a second app
```

Depth inside Library is unchanged: calendar, then the grid, then the picture. Back and Escape walk back one step. Search, tasks, and settings stay sheets so the pictures remain the page.

Home is the first arrival even after pictures exist, so a person always has a place that says what to do next. Library is one click away.

## First arrival

When there are no pictures yet, Home is a single reading surface:

1. One sentence: there is more to remember.
2. One action: **Add a folder**.
3. Three steps: add pictures, point at a detail, name someone only when sure.
4. Three doors: Library, Visual discovery, People. Each says what it is for, and Visual discovery says to add a folder first.
5. A quieter list, **Explore all capabilities**, for everything else.

Nothing on that page names a database, a model file, or an internal search mode.

## Design system

Name: **Safelight Desk**. A private desk for pictures, not a dashboard.

| Token | Use |
|---|---|
| Existing atmosphere colours | Canvas, spine, accent, danger, warning. Themes stay selectable. Clean install stays Mica Dark. |
| `Noto Serif` | The promise, the month, the product name |
| `Inter` | Controls, search, body. Falls back when the face is missing. |
| Hairline rules and a 3px accent mark | Selection. No heavy card chrome. |
| Dark ink on a bright accent fill | The one primary button, so the label stays readable |
| 16px stage margin, left-aligned reading column | Home. Not a centred marketing stack. |

Motion stays on the existing reduced-motion switch. Hover and selection stay different: hover is a faint wash, selection is the accent mark plus accent type.

## Key flows

**Add pictures.** Home or spine → choose a folder → the task sheet says what is happening, with Pause and Cancel. Pictures already added can still be opened.

**Find a detail.** Library → open a picture → point or draw → the bottom tray says it is looking, then shows matches with the place marked. Cancel and Escape drop a late result.

**Name someone.** People → choose a group → type a name. Until that, the group stays a suggestion. The note on the page says so.

**Something went wrong.** A banner at the top of the stage says what happened, in a sentence, and that the original files were not changed. Loading and “not available” use different sentences.

**Empty.** No pictures: Home. No groups: People explains the next step. An empty day says there are no photos that day and offers Back.

## Components

| Component | Job |
|---|---|
| `Shell.qml` spine | Home, Library, People, Add folder, Settings. Search when not on Home. |
| `HomeLaunchpad.qml` | First arrival and return desk. Keeps the same actions. |
| Calendar / year / timeline | Time browsing. Unchanged structure. Serif month title. |
| Picture view | The photo, the selection, the match tray, details on demand. |
| `peopleDesk` | Groups, then one group, then a name. |
| Settings sheet | Look, how much to show, what is ready. |
| Task sheet | Work in progress. |
| Notice banner | Error, unavailable, and working. |

## Copy rules

- Buttons are verbs a person can picture: Add a folder, Find this on my screen, See these photos.
- “Capabilities”, “mode”, and “model” stay out of everyday labels. Settings says what is ready on this computer.
- Advanced details may stay one step away. Everyday mode does not show engine names.
- Progress never invents a percentage the work did not report.

## Out of this pass

Identity thresholds, schema, and the face comparison path stay as they are. No second window toolkit. No cloud account.
