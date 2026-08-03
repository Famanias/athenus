PHASE 1
Edge Case Scenario	Test Action	Expected Result	Success Indicator
1. Multiple Video Uploads	Upload lecture_1.mp4, then lecture_2.mp4	Both videos are saved in SQLite media_items table. Both appear in Library Grid.	Library lists 2 assets; both transcripts accessible.
2. Duplicate Video Upload	Upload the exact same file twice	New media_id UUID generated; both records saved cleanly without SQL collision.	Both uploads succeed with unique media_id.
3. Manual Chat Clear	Click Clear Chat button in header	Conversation thread resets to default welcome message.	Thread clears; typing a new question starts fresh session.
4. Backend Unavailable	Stop backend (Ctrl+C), type chat question	UI shows a red error banner: Backend Service Unavailable....	Graceful error notification; application does not crash.
5. Interrupted Ingestion	Kill backend process mid-transcription	Status in SQLite stays at last stage (transcribing / failed).	Upon restart, item shows error or failed status cleanly.
6. Workspace Switching	Create new workspace, switch back & forth	Workspaces and media IDs are loaded from SQLite workspaces table.	Each workspace maintains its own isolated metadata list.

PHASE 2

Edge Case Scenario	Action / State	Internal Execution	Expected Behavior
1. Dual Workspace Queries	Query Workspace A for content stored only in Workspace B	Qdrant Filter applies must: [workspace_id == "Workspace_A"]	0 hits from Workspace B returned; no context leakage
2. Scoped Video Query	Pass both workspace_id AND media_id	Qdrant Filter applies must: [workspace_id == "A", media_id == "M1"]	Search is restricted strictly to that specific video within Workspace A
3. Empty Workspace Search	Search a new workspace with no indexed videos	Qdrant search returns empty hits list []	Assistant gracefully reports no relevant video context found
4. Multi-Video Workspace Search	Search workspace with 5 videos without specifying media_id	Qdrant Filter matches all points matching workspace_id == "Workspace_A"	Returns top hits across all 5 videos within Workspace A
5. Identical Queries in Different Workspaces	Ask "Explain gradient descent" in Workspace A vs Workspace B	Each query executes with its respective workspace filter	Context passages and citation timestamps match only the active workspace