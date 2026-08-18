# pytest-given — pytest-given

## ✓ A «scenario» records under its «node ID»
`tests/unit/capture/test_collector.py:23::test_start_and_finish_scenario` · happy-path

- **given** a fresh «Collector»
- **when** a «Scenario» starts under its «Node ID» and finishes
- **then** it carries its «Node ID», name, status, duration and «Tag»

## ✓ «Steps» record with their «phases»
`tests/unit/capture/test_collector.py:43::test_collect_steps` · happy-path

- **given** an «Active scenario» in a fresh «Collector»
- **when** a given and a when «Step» are pushed
- **then** each «Step» carries its «Phase»

## ✓ «Steps» pushed during fixture setup record into the «fixture recording»
`tests/unit/capture/test_collector.py:213::test_push_step_during_fixture_setup_records_into_recording` · happy-path

- **given** a «Fixture recording» under setup
- **when** a «Step» is pushed inside the fixture body
- **then** it is recorded as a child of the recording root

## ✓ An «attachment» lands on the «step» being recorded
`tests/unit/capture/test_collector.py:234::test_attach_during_fixture_setup_records_into_recording` · happy-path

- **given** a «Fixture recording» under setup
- **when** an «Attachment» is attached inside the fixture body
- **then** the «Attachment» lands on the recording root

## ✓ Fixture-body «steps» do not leak into the «active scenario»
`tests/unit/capture/test_collector.py:253::test_push_step_routing_isolates_recording_from_scenario` · happy-path

- **given** an «Active scenario» with a «Fixture recording»
- **when** a «Step» is pushed inside the fixture body
- **then** the step lives only in the recording, not the scenario

## ✓ A «fixture recording» is deep-copied when «grafted»
`tests/unit/capture/test_collector.py:316::test_graft_recording_deep_copies_into_scenario` · happy-path

- **given** a «Fixture recording» with a nested child «Step»
- **when** a «Graft» copies it into the «Active scenario»
- **then** the scenario gains a deep copy of the recorded steps

## ✓ A leaf given is «grafted» as a childless given «step»
`tests/unit/capture/test_collector.py:458::test_graft_leaf_given_appends_childless_given_step` · happy-path

- **given** an «Active scenario» is being recorded
- **when** a leaf «Graft» appends a childless «Step»
- **then** the step is a given with no children

## ✓ «Grafting» with an override replaces the root label but keeps children
`tests/unit/capture/test_collector.py:477::test_graft_recording_override_replaces_root_narration_keeps_children` · happy-path

- **given** a «Fixture recording» whose root has a label and a child
- **when** a «Graft» supplies an override «Narration»
- **then** the grafted root shows the override text and keeps its children

## ✓ «Grafting» with no «active scenario» is a no-op
`tests/unit/capture/test_collector.py:503::test_graft_leaf_given_without_scenario_is_noop` · happy-path

- **given** a collector with no «Active scenario»
- **when** a leaf «Graft» runs
- **then** no scenario is recorded

## ✓ «FileGlossary» lookup is case-insensitive
`tests/unit/capture/test_file_glossary.py:27::test_lookup_is_case_insensitive` · happy-path

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «Term» is looked up in three different cases
- **then** every lookup resolves to one handle type and the same id

## ✓ Repeated lookups return the same handle
`tests/unit/capture/test_file_glossary.py:42::test_handles_are_memoized` · happy-path

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** the same «Term» is looked up twice
- **then** both lookups return the one memoized handle

## ✓ File-loaded «terms» start «kindless»
`tests/unit/capture/test_file_glossary.py:56::test_terms_start_kindless` · happy-path

- **given** a Markdown glossary file with no kind column
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a «File glossary» loads it
- **then** each «Term» is «Kindless» until «Kind inference» runs

## ✓ An unknown name raises with a suggestion
`tests/unit/capture/test_file_glossary.py:73::test_unknown_name_raises_with_suggestion` · validation

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a misspelt «Term» is looked up
- **then** a PytestGivenError is raised with a spelling hint

## ✓ Handles are usable inline in an «activity»
`tests/unit/capture/test_file_glossary.py:91::test_usable_inline_in_activity` · story-grammar

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** its handles build an «Activity»
- **then** each slot becomes a «Term ref»

## ✓ Calling a handle overrides its display
`tests/unit/capture/test_file_glossary.py:108::test_call_overrides_display` · story-grammar

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a handle is called to name an «Instance»
- **then** the «Term ref» carries the overridden display

## ✓ An explicit kind column sets «term» kinds
`tests/unit/capture/test_file_glossary.py:128::test_explicit_kind_column` · happy-path

- **given** a Markdown glossary with an explicit Kind column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «File glossary» reads the Kind column
- **then** kinds come straight from the file, not «Kindless» inference

## ✓ A kind column can be selected by integer index
`tests/unit/capture/test_file_glossary.py:148::test_kind_column_by_integer_index` · happy-path

- **given** a Markdown glossary with the kind in the third column
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Actor |
    | Room | y | Work Object |
    ```
- **when** the «File glossary» selects the kind column by index
- **then** the kinds are read from that column

## ✓ A «work_object» kind alias maps to the object kind
`tests/unit/capture/test_file_glossary.py:168::test_work_object_underscore_alias` · happy-path

- **given** a glossary whose Kind cell says work_object
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Room | y | work_object |
    ```
- **when** the «File glossary» parses the kind
- **then** it normalizes to the «Work Object» kind

## ✓ An unrecognised kind value is rejected
`tests/unit/capture/test_file_glossary.py:184::test_unrecognised_kind_value_raises` · validation

- **given** a glossary whose Kind cell holds an unknown value
  - 📎 Glossary file:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | Wizard |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError names the unrecognised kind

## ✓ A missing «glossary» file is reported clearly
`tests/unit/capture/test_file_glossary.py:204::test_missing_file_raises` · validation

- **given** a path to a file that does not exist
- **when** a «File glossary» is opened on that path
- **then** a PytestGivenError reports the file is not found

## ✓ A «term» cell with no alphanumeric characters is rejected
`tests/unit/capture/test_file_glossary.py:231::test_empty_id_term_cell_raises` · validation

- **given** a row whose «Term» cell has no id-able characters
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | @#$ | some definition |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError is raised with file:line context

## ✓ Conflicting duplicate rows are rejected
`tests/unit/capture/test_file_glossary.py:251::test_conflicting_duplicate_rows_raise` · validation

- **given** two rows for one «Term» with different definitions
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | First definition. |
    | Guest | Second definition. |
    ```
- **when** the «File glossary» loads the file
- **then** a PytestGivenError reports the conflicting rows

## ✓ A blank description normalizes to «undefined»
`tests/unit/capture/test_file_glossary.py:275::test_blank_description_cell_normalizes_to_none` · happy-path

- **given** a row whose description cell is blank
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest |   |
    ```
- **when** the «File glossary» parses it
- **then** the «Term» definition is None, i.e. «Undefined»

## ✓ Identical duplicate rows collapse to one «term»
`tests/unit/capture/test_file_glossary.py:293::test_idempotent_duplicate_rows_ok` · happy-path

- **given** two identical rows for the same «Term»
  - 📎 Glossary file:
    ```
    | Term | Meaning |
    |---|---|
    | Guest | A person booking. |
    | Guest | A person booking. |
    ```
- **when** the «File glossary» parses them
- **then** they collapse to a single «Term»

## ✓ Calling «FileGlossary» looks up a known «term»
`tests/unit/capture/test_file_glossary.py:319::test_file_glossary_call_known_name_returns_handle` · happy-path

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** a known «Term» is looked up by call
- **then** a «Deferred term» is returned

## ✓ «FileGlossary» is a closed vocabulary
`tests/unit/capture/test_file_glossary.py:334::test_file_glossary_call_unknown_name_raises` · validation

- **given** a «File glossary» loaded from a Markdown file
  - 📎 Glossary file:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest  | A person booking. |
    | Room   | A bookable room. |
    | search | Look up options. |
    ```
- **when** an unknown name is called
- **then** a PytestGivenError is raised
- **then** no new «Term» was created

## ✓ Calling an «actor» names a distinct «instance»
`tests/unit/capture/test_glossary.py:106::test_actor_call_returns_instance_with_distinct_display` · happy-path

- **given** an «Actor» handle for Guest
- **when** the «Actor» is called with a name
- **then** an «Instance» with a distinct display is returned

## ✓ Calling a «verb» records an «inflection» of the same «term»
`tests/unit/capture/test_glossary.py:133::test_verb_call_returns_inflection_sharing_term_identity` · happy-path

- **given** a «Verb» handle for confirm
- **when** the «Verb» is called with a surface form
- **then** an «Inflection» sharing the verb identity is returned

## ✓ Registering an «actor» returns a typed handle
`tests/unit/capture/test_glossary.py:154::test_glossary_actor_registers_and_returns_handle` · happy-path

- **given** an empty glossary
- **when** an «Actor» is registered with a definition
- **then** a typed «Actor» handle with the «Actor» kind is returned

## ✓ Re-registering a «term» with matching fields is idempotent
`tests/unit/capture/test_glossary.py:186::test_glossary_re_registration_with_matching_fields_is_idempotent` · happy-path

- **given** an «Actor» already registered with a definition
- **when** the same name and definition are registered again
- **then** both handles share the one «Term»

## ✓ Re-registering a «term» with a different definition is rejected
`tests/unit/capture/test_glossary.py:201::test_glossary_re_registration_with_mismatched_definition_raises` · validation

- **given** an «Actor» already registered with one definition
- **when** the name is registered again with a different definition
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ The same name cannot be two different kinds
`tests/unit/capture/test_glossary.py:219::test_glossary_cross_kind_collision_raises` · validation

- **given** a name already registered as an «Actor»
- **when** the same name is registered as a «Verb»
- **then** a PytestGivenError reports the conflict with the prior registration

## ✓ Registering an «actor» captures its definition site
`tests/unit/capture/test_glossary.py:243::test_glossary_actor_captures_source` · happy-path

- **given** a rootdir-aware glossary
- **when** an «Actor» is registered
- **then** the «Term» records a «Source link» to this file

## ✓ Calling the «glossary» declares a «kindless» «term»
`tests/unit/capture/test_glossary.py:338::test_call_declares_kindless_term` · happy-path

- **given** an empty glossary
- **when** a «Term» is declared by call, without a kind
- **then** the «Term» is registered as «Kindless»

## ✓ Subscript looks up an already-declared «term»
`tests/unit/capture/test_glossary.py:418::test_subscript_get_only_returns_handle` · happy-path

- **given** a glossary with one declared «Term»
- **when** the name is looked up by subscript
- **then** the returned «Term» is the declared one

## ✓ Subscripting an unknown name raises with a hint
`tests/unit/capture/test_glossary.py:432::test_subscript_unknown_name_raises_with_hint` · validation

- **given** a glossary with one declared «Term»
- **when** a near-miss name is subscripted
- **then** a PytestGivenError is raised with a spelling hint

## ✓ «Term» kinds are inferred from activity-slot positions
`tests/unit/capture/test_kind_inference.py:46::test_infers_actor_verb_object_by_position` · happy-path

- **given** a glossary of three «Kindless» «Term» entries
- **when** «Kind inference» runs over a «Story»
- **then** they are inferred as «Actor», «Verb», «Work Object» by slot

## ✓ An «actor» «slot» anywhere wins over a noun «slot» elsewhere
`tests/unit/capture/test_kind_inference.py:65::test_actor_anywhere_beats_object` · happy-path

- **given** a «Term» that sits in a noun slot in one «Story»
- **when** the same «Term» also appears in an «Actor» slot
- **then** its inferred kind is «Actor»

## ✓ A «term» used in no «story» stays «kindless»
`tests/unit/capture/test_kind_inference.py:86::test_never_used_stays_kindless` · happy-path

- **given** a «Term» referenced by no «Story»
- **when** «Kind inference» runs with no stories
- **then** the «Term» remains «Kindless»

## ✓ A «term» in both a «verb» and a noun «slot» is a conflict
`tests/unit/capture/test_kind_inference.py:99::test_verb_and_noun_conflict_raises` · validation

- **given** a «Kindless» «Term» used in a verb slot and a noun slot
- **when** kind resolution runs over both stories
- **then** a PytestGivenError names the conflicting term

## ✓ A declared kind consistent with its «slot» is kept
`tests/unit/capture/test_kind_inference.py:121::test_declared_kind_verified_and_kept` · happy-path

- **given** a glossary with explicitly declared «Term» kinds
- **when** «Kind inference» runs over a matching «Story»
- **then** the declared kinds are verified and preserved

## ✓ A declared «verb» in an «actor» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:144::test_declared_verb_in_actor_slot_raises` · validation

- **given** a «Term» declared as a «Verb»
- **when** kind resolution places it in the «Actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A «term» used as both «verb» and «actor» is a conflict
`tests/unit/capture/test_kind_inference.py:161::test_verb_and_actor_conflict_raises` · validation

- **given** a «Kindless» «Term» used in a verb slot and an actor slot
- **when** kind resolution runs over both stories
- **then** a PytestGivenError names the conflicting term

## ✓ A declared «work object» in an «actor» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:187::test_declared_object_in_actor_slot_raises` · validation

- **given** a «Term» declared as a «Work Object»
- **when** kind resolution places it in the «Actor» slot
- **then** a PytestGivenError names the misplaced term

## ✓ A declared «actor» in a «verb» «slot» is rejected
`tests/unit/capture/test_kind_inference.py:205::test_declared_actor_in_verb_slot_raises` · validation

- **given** a «Term» declared as an «Actor»
- **when** kind resolution places it at position 1 (the verb slot)
- **then** a PytestGivenError says an actor cannot fill the verb slot

## ✓ A conflict error names only the offending «stories»
`tests/unit/capture/test_kind_inference.py:224::test_conflict_where_names_only_offending_stories` · validation

- **given** an «Actor» «Term» that also appears in a verb slot
- **when** kind resolution raises
- **then** only the offending story is named in the message

## ✓ A conflict message excludes «stories» with an unrelated «slot»
`tests/unit/capture/test_kind_inference.py:244::test_inferred_conflict_where_excludes_unrelated_slot_stories` · validation

- **given** a «Kindless» «Term» used in verb, actor and noun slots
- **when** the verb-vs-actor conflict is raised
- **then** only the verb and actor stories are named, not the noun one

## ✓ A declared «verb» in a noun «slot» is rejected
`tests/unit/capture/test_kind_inference.py:267::test_declared_verb_in_noun_slot_raises` · validation

- **given** a «Term» declared as a «Verb»
- **when** kind resolution places it at position ≥2 (a noun slot)
- **then** a PytestGivenError says a verb cannot fill the noun slot

## ✓ «Slot» positions alternate verb/noun after the «actor»
`tests/unit/capture/test_kind_inference.py:286::test_slot_for_maps_odd_positions_to_verb` · happy-path

- **given** the five positions of a short activity path
- **when** the «Slot» rule is applied to each position
- **then** position 0 is the actor «Slot», then verb and noun alternate

## ✓ A pipe table parses into «term» and definition rows
`tests/unit/capture/test_markdown_glossary.py:24::test_parses_default_columns` · markdown, happy-path

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser reads it into rows for a «File glossary»
- **then** each row carries a «Term», definition and source line

## ✓ Multiple tables in one file are merged
`tests/unit/capture/test_markdown_glossary.py:42::test_merges_multiple_tables` · markdown, happy-path

- **given** a document containing two separate pipe tables
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    
    ## More
    
    | Term | Meaning |
    |---|---|
    | Search | Look up. |
    ```
- **when** the parser reads the whole document
- **then** every table contributes its «Term» rows

## ✓ Columns can be selected by header name
`tests/unit/capture/test_markdown_glossary.py:61::test_column_by_header_name_case_insensitive` · markdown, happy-path

- **given** a table with custom, differently-cased header names
  - 📎 Markdown document:
    ```
    | Word | Note | Role |
    |---|---|---|
    | Guest | x | Actor |
    ```
- **when** the parser selects columns by header name
- **then** the named columns are matched case-insensitively

## ✓ Escaped pipes are preserved in cells
`tests/unit/capture/test_markdown_glossary.py:77::test_escaped_pipe_in_cell` · markdown, happy-path

- **given** cells containing escaped pipe characters (\|)
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | A\|B | pipe\|here |
    ```
- **when** the parser splits the row
- **then** the escaped pipe survives as a literal pipe

## ✓ Tables inside fenced code blocks are skipped
`tests/unit/capture/test_markdown_glossary.py:95::test_skips_tables_in_fenced_code_blocks` · markdown, happy-path

- **given** a fenced code block that contains a look-alike table
  - 📎 Markdown document:
    ````
    ```
    | Term | Meaning |
    |---|---|
    | Fake | nope |
    ```
    
    | Term | Meaning |
    |---|---|
    | Real | yes |
    ````
- **when** the parser reads the document
- **then** only the real table outside the fence contributes rows

## ✓ A file with no pipe table is rejected
`tests/unit/capture/test_markdown_glossary.py:114::test_no_table_raises` · markdown, validation

- **given** a document with no pipe table
  - 📎 Markdown document:
    ```
    # Just a heading
    
    No tables here.
    ```
- **when** the parser reads it for a «File glossary»
- **then** no pipe table is reported

## ✓ A missing named column is rejected
`tests/unit/capture/test_markdown_glossary.py:134::test_missing_named_column_raises` · markdown, validation

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser selects a header name that is absent
- **then** a PytestGivenError names the missing column

## ✓ A column index out of range is rejected
`tests/unit/capture/test_markdown_glossary.py:151::test_index_out_of_range_raises` · markdown, validation

- **given** a Markdown document with one pipe table
  - 📎 Markdown document:
    ```
    # Glossary
    
    | Term | Meaning |
    |------|---------|
    | Guest | A person booking. |
    | Room  | A bookable room. |
    ```
- **when** the parser selects a column index past the table width
- **then** a PytestGivenError names the out-of-range column

## ✓ A data row with too few columns is rejected
`tests/unit/capture/test_markdown_glossary.py:175::test_data_row_with_fewer_columns_raises` · markdown, validation

- **given** a table with a data row narrower than its header
  - 📎 Markdown document:
    ```
    | Term | Meaning | Type |
    |---|---|---|
    | Guest | A person |
    | Room | A bookable room | place |
    ```
- **when** the parser reads the short row
- **then** a PytestGivenError points at the short row

## ✓ Bold «term» cells render as clean «terms»
`tests/unit/capture/test_markdown_glossary.py:193::test_strips_bold_from_term_cell` · markdown, happy-path

- **given** a «Term» cell written with **bold** emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | **Scenario** | A decorated test. |
    ```
- **when** the parser reads the term cell
- **then** the emphasis is unwrapped to the plain canonical

## ✓ Italic and inline-code «term» cells are unwrapped
`tests/unit/capture/test_markdown_glossary.py:213::test_strips_italic_and_inline_code_from_term_cell` · markdown, happy-path

- **given** «Term» cells using *italic* and `code` emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | *Step* | one. |
    | `given` | two. |
    ```
- **when** the parser reads the term cells
- **then** each unwraps to its plain text

## ✓ Underscores inside an identifier survive
`tests/unit/capture/test_markdown_glossary.py:229::test_preserves_underscores_inside_term_identifier` · markdown, happy-path

- **given** a «Term» literally named work_object
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | work_object | a thing. |
    ```
- **when** the parser reads the term cell
- **then** the single underscores are not treated as emphasis

## ✓ Emphasis is stripped from kind cells too
`tests/unit/capture/test_markdown_glossary.py:245::test_strips_emphasis_from_kind_cell` · markdown, happy-path

- **given** a Kind cell written with bold emphasis
  - 📎 Markdown document:
    ```
    | Term | Meaning | Kind |
    |---|---|---|
    | Guest | x | **Actor** |
    ```
- **when** the parser reads the kind cell
- **then** the kind is unwrapped to plain text

## ✓ Definition markdown is left intact
`tests/unit/capture/test_markdown_glossary.py:261::test_leaves_description_markdown_intact` · markdown, happy-path

- **given** a definition cell rich with inline code
  - 📎 Markdown document:
    ```
    | Term | Meaning |
    |---|---|
    | Scenario | A test decorated with `@scenario(...)`. |
    ```
- **when** the parser reads the row
- **then** the definition keeps its markup for the tooltip

## ✓ A pipe line without a separator is not a table
`tests/unit/capture/test_markdown_glossary.py:280::test_pipe_line_without_separator_is_skipped` · markdown, happy-path

- **given** prose containing a stray pipe, then a real table
  - 📎 Markdown document:
    ```
    This line has a | in it but no separator follows.
    Next line is not a separator.
    
    | Term | Meaning |
    |---|---|
    | Real | yes |
    ```
- **when** the parser reads the document
- **then** only the real pipe table produces rows

## ✓ A «step» pairs its «narration» with a «phase»
`tests/unit/capture/test_step_descriptor.py:54::test_context_manager_basic` · happy-path

- **when** a given «Step» descriptor is created
- **then** it carries the given «Phase» and its «Narration»

## ✓ «when_then» records the action and its outcome as siblings
`tests/unit/capture/test_step_descriptor.py:249::test_when_then_records_two_sibling_steps_on_clean_exit` · happy-path

- **given** an «Active scenario» in a local «Collector»
- **when** a «when_then» block exits cleanly
- **then** a when and a sibling then «Step» are recorded

## ✓ «when_then» pairs with an inner pytest.raises
`tests/unit/capture/test_step_descriptor.py:278::test_when_then_pairs_with_inner_pytest_raises` · happy-path

- **given** an «Active scenario» in a local «Collector»
- **when** the «when_then» body raises and an inner pytest.raises swallows it
- **then** both sibling steps are still recorded

## ✓ «when_then» omits the then when the body raises uncaught
`tests/unit/capture/test_step_descriptor.py:309::test_when_then_omits_then_when_body_raises_uncaught` · validation

- **given** an «Active scenario» in a local «Collector»
- **when** the «when_then» body raises with nothing catching inside
- **then** only the when step is recorded — the outcome never held

## ✓ A nested when becomes a child of the «when_then» action
`tests/unit/capture/test_step_descriptor.py:389::test_when_then_allows_nested_when_as_child_sub_step` · happy-path

- **given** an «Active scenario» in a local «Collector»
- **when** a when opens inside the «when_then» body
- **then** the sub-action is a child of the action and the then still follows

## ✓ An «actor» handle in a «path» becomes a «term ref»
`tests/unit/capture/test_story.py:54::test_path_dispatches_actor_to_activity_term_ref` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built from three glossary handles
- **then** the «Actor» slot becomes a «Term ref»

## ✓ An inflected «verb» keeps its «term» identity but shows the «inflection»
`tests/unit/capture/test_story.py:98::test_path_dispatches_inflected_verb_to_activity_term_ref_with_inflected_display` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a «Verb» handle called with an «Inflection»
- **when** it takes the verb slot of a «Path»
- **then** the «Term ref» shows the inflection over the same «Verb»

## ✓ A bare string in a «path» becomes a connective word
`tests/unit/capture/test_story.py:116::test_path_dispatches_bare_string_to_activity_word` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built with a bare word between term nodes
- **then** the bare word becomes an «Activity Part» word, not a «Term ref»

## ✓ A «path» needs at least an «actor», a «verb» and a node
`tests/unit/capture/test_story.py:132::test_path_rejects_path_with_fewer_than_three_parts` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **when** a «Path» of only two parts is built
- **then** a PytestGivenError rejects it as too short

## ✓ Position 0 of a «path» must be an «actor»
`tests/unit/capture/test_story.py:148::test_path_rejects_work_object_in_position_0` · story-grammar, validation

- **given** a search verb
- **given** a Room work object
- **when** a «Path» is built with a «Work Object» in position 0
- **then** a PytestGivenError says position 0 is the «Actor» slot

## ✓ A «verb» cannot open a «path»
`tests/unit/capture/test_story.py:163::test_path_rejects_verb_in_position_0` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Verb» is placed in position 0 of a «Path»
- **then** a PytestGivenError says position 0 is the «Actor» slot

## ✓ A bare string may stand in for the «actor» «slot»
`tests/unit/capture/test_story.py:178::test_path_allows_bare_string_in_position_0` · story-grammar, happy-path

- **given** a search verb
- **given** a Room work object
- **when** a bare string takes position 0 of a «Path»
- **then** it is accepted as an «Activity Part» word

## ✓ Position 1 of a «path» must be a «verb»
`tests/unit/capture/test_story.py:189::test_path_rejects_actor_in_position_1` · story-grammar, validation

- **given** a Guest actor
- **given** a Room work object
- **when** an «Actor» is placed in position 1 of a «Path»
- **then** a PytestGivenError says position 1 is the «Verb» slot

## ✓ A «work object» cannot fill the «verb» «slot»
`tests/unit/capture/test_story.py:204::test_path_rejects_work_object_in_position_1` · story-grammar, validation

- **given** a Guest actor
- **given** a Room work object
- **when** a «Work Object» is placed in position 1 of a «Path»
- **then** a PytestGivenError says position 1 is the «Verb» slot

## ✓ Position 2 of a «path» must be a noun
`tests/unit/capture/test_story.py:219::test_path_rejects_verb_in_position_2` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **when** a «Verb» is placed in position 2 of a «Path»
- **then** a PytestGivenError says position 2 is the noun slot

## ✓ A bare «verb» may sit between two real entity nodes
`tests/unit/capture/test_story.py:234::test_path_allows_bare_verb_between_term_nodes` · story-grammar, happy-path

- **given** a Guest actor
- **given** a Room work object
- **when** a bare verb sits between an «Actor» and a «Work Object»
- **then** the entities are term refs and the verb stays a bare word

## ✓ A «path» may be fully bare words
`tests/unit/capture/test_story.py:250::test_path_allows_fully_bare_path` · story-grammar, happy-path

- **given** three plain words with no glossary handles
- **when** a «Path» is built from them
- **then** every part is an «Activity Part» word

## ✓ Node/edge alternation allows a trailing connective node
`tests/unit/capture/test_story.py:270::test_path_allows_node_edge_alternation_with_connective` · story-grammar, happy-path

- **given** an «Actor», a «Verb», a «Work Object» and a second actor
- **when** they form a five-part «Path» joined by a connective
- **then** even positions are term-ref nodes and the connective stays a word

## ✓ A «path» may not end on a dangling edge
`tests/unit/capture/test_story.py:296::test_path_rejects_dangling_edge` · story-grammar, validation

- **given** an «Actor», «Verb» and «Work Object» plus a connective
- **when** a path ending on a connective edge is built
- **then** a PytestGivenError rejects the dangling edge

## ✓ A single-path «activity» synthesizes one «path»
`tests/unit/capture/test_story.py:321::test_activity_single_path_synthesizes_one_path` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** an «Activity» is built from handles directly
- **then** it wraps a single «Path»

## ✓ An «activity» may branch into multiple «paths»
`tests/unit/capture/test_story.py:335::test_activity_multi_path_accepts_multiple_paths` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two alternate «Path» branches
- **when** they are combined into one «Activity»
- **then** the activity carries both paths

## ✓ Mixing loose parts and prebuilt «paths» is rejected
`tests/unit/capture/test_story.py:350::test_activity_mixing_parts_and_paths_raises` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a prebuilt «Path»
- **when** it is combined with loose handles in one «Activity»
- **then** a PytestGivenError rejects the mix

## ✓ «Activity» id 0 is reserved
`tests/unit/capture/test_story.py:367::test_activity_explicit_id_zero_raises` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** an «Activity» is built with explicit activity_id=0
- **then** a PytestGivenError says activity_id=0 is reserved

## ✓ A «story» auto-numbers its «activities» from one
`tests/unit/capture/test_story.py:385::test_story_auto_numbers_activities_from_one` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **when** a «Story» is built from two «Activity» rows
- **then** the activities are numbered 1 and 2

## ✓ Auto-numbering skips ids already taken explicitly
`tests/unit/capture/test_story.py:401::test_story_auto_numbering_skips_taken_explicit_ids` · story-grammar, happy-path

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** a mix of explicit and auto «Activity» ids
- **when** they are assembled into a «Story»
- **then** auto picks skip the ids already used explicitly

## ✓ Duplicate «activity» ids in a «story» are rejected
`tests/unit/capture/test_story.py:419::test_story_rejects_duplicate_activity_ids` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two «Activity» rows sharing an explicit id
- **when** they are assembled into a «Story»
- **then** a PytestGivenError reports the duplicate activity id

## ✓ A «story» derives its id from its title
`tests/unit/capture/test_story.py:439::test_story_derives_id_from_title` · story-grammar, happy-path

- **given** a human-readable story title
- **when** a «Story» is built from it
- **then** its id is the slugified title

## ✓ A «story» may span only one «glossary»
`tests/unit/capture/test_story.py:452::test_story_rejects_two_glossaries` · story-grammar, validation

- **given** a Guest actor
- **given** a search verb
- **given** a Room work object
- **given** two activities that reach two different glossaries
- **when** a «Story» is built spanning both glossaries
- **then** a PytestGivenError says a story spans multiple glossaries

## ✓ Two «stories» with the same id collide
`tests/unit/capture/test_story.py:498::test_story_id_collision_raises_with_both_sites` · story-grammar, validation

- **given** a «Story» already declared under an id
- **when** a second story is declared with the same slug
- **then** a PytestGivenError reports the id was already declared

## ✓ A «path» may chain a second verb-object pair
`tests/unit/capture/test_story.py:568::test_path_allows_second_verb_edge` · story-grammar, happy-path

- **given** an «Actor», two «Verb» and two «Work Object» handles
- **when** they form a five-node «Path» (actor verb object verb object)
- **then** every slot is a «Term ref», with no bare words

## ✓ A Template parses a bare placeholder
`tests/unit/capture/test_template.py:35::test_template_parses_single_placeholder` · step-text, parametrization

- **given** a deferred «Templatize» template with one placeholder
- **when** the template is parsed
- **then** it splits into literal and placeholder «Narration» parts

## ✓ A Template substitutes parametrize values
`tests/unit/capture/test_template.py:73::test_template_substitute_basic` · step-text, parametrization

- **given** a «Templatize» template referencing a «Case» column
- **when** a «Parameter table» value is substituted in
- **then** the placeholder is filled with that value

## ✓ A t-string interpolation becomes a value part
`tests/unit/capture/test_template.py:141::test_parse_tstring_single_interpolation` · step-text, happy-path

- **given** a t-string step with one interpolated value
- **when** the t-string is parsed at runtime
- **then** the interpolation becomes a «Narration» value part

## ✓ A t-string can interpolate an arbitrary expression
`tests/unit/capture/test_template.py:205::test_parse_tstring_expression` · step-text, happy-path

- **given** a t-string step interpolating a computed expression
- **when** the t-string is parsed
- **then** the «Value highlight» part records the full expression

## ✓ A «glossary» handle in a t-string emits a «term ref»
`tests/unit/capture/test_template.py:245::test_tstring_with_actor_emits_term_ref` · step-text

- **given** an «Actor» handle from the glossary
- **when** the handle is interpolated into a t-string step
- **then** the step carries a «Term ref» pill for that «Actor»

## ✓ A «work object» handle in a t-string emits a «term ref»
`tests/unit/capture/test_template.py:275::test_tstring_with_work_object_emits_term_ref` · step-text

- **given** a «Work Object» handle from the glossary
- **when** it is interpolated into a t-string step
- **then** the step carries a «Term ref» for that «Work Object»

## ✓ A bare «verb» handle keeps its canonical display
`tests/unit/capture/test_template.py:297::test_tstring_with_verb_emits_term_ref_with_canonical_display` · step-text

- **given** a «Verb» handle used without an «Inflection»
- **when** it is interpolated into a t-string step
- **then** the «Term ref» shows the canonical verb

## ✓ An inflected «verb» in a t-string shows the «inflection»
`tests/unit/capture/test_template.py:313::test_tstring_with_inflected_verb_emits_term_ref_with_inflected_display` · step-text

- **given** a «Verb» handle called with an «Inflection»
- **when** it is interpolated into a t-string step
- **then** the «Term ref» shows the inflection but keeps the verb id

## ✓ A «term ref» may not carry a format spec
`tests/unit/capture/test_template.py:354::test_tstring_term_ref_with_format_spec_raises` · step-text, validation

- **given** an «Actor» handle interpolated with a format spec
- **when** the t-string is parsed
- **then** a PytestGivenError says a «Term ref» takes no format spec

## ✓ A «FileGlossary» handle works in a t-string «step»
`tests/unit/capture/test_template.py:397::test_tstring_with_file_term_handle_emits_term_ref` · step-text

- **given** a «Deferred term» from a «File glossary»
- **when** it is interpolated into a t-string step
- **then** the step carries a single «Term ref» pill

## ✓ The «glossary» view aggregates «instances» and «verb» forms
`tests/unit/report/test_aggregations.py:160::test_build_glossary_aggregations_collects_instances_and_forms` · happy-path

- **given** a «Report» whose «Story» and «Scenario» reference entity «Instance»s and an «Inflection»
  - 📎 Report data:
    ```
    {
      "metadata": {
        "project": "p",
        "timestamp": "t",
        "pytest_version": "8",
        "plugin_version": "0",
        "commit_sha": null
      },
      "scenarios": [
        {
          "id": "t",
          "narration": {
            "text": "s",
            "parts": []
          },
          "module": "m",
          "tags": [],
          "status": "passed",
          "duration_ms": 0,
          "steps": [
            {
              "phase": "when",
              "narration": {
                "text": "x",
                "parts": [
                  {
                    "term_id": "guest",
                    "display": "Alice",
                    "expression": "",
                    "param_column": null
                  },
                  {
                    "term_id": "search",
                    "display": "searches",
                    "expression": "",
                    "param_column": null
                  },
                  {
                    "term_id": "room",
                    "display": "Deluxe Suite",
                    "expression": "",
                    "param_column": null
                  }
                ]
              },
              "status": "passed",
              "children": [],
              "attachments": [],
              "error": null,
              "activity_ids": [],
              "fixture_name": null
            }
          ],
          "parameters": null,
          "error": null,
          "skip_reason": null,
          "source": null,
          "story_id": "book",
          "activity_ids": []
        }
      ],
      "glossary": {
        "terms": [
          {
            "id": "guest",
            "kind": "actor",
            "canonical": "Guest",
            "definition": null,
            "source": null
          },
          {
            "id": "room",
            "kind": "object",
            "canonical": "Room",
            "definition": null,
            "source": null
          },
          {
            "id": "search",
            "kind": "verb",
            "canonical": "search",
            "definition": null,
            "source": null
          }
        ]
      },
      "stories": [
        {
          "id": "book",
          "title": "Book",
          "activities": [
            {
              "id": 1,
              "paths": [
                {
                  "parts": [
                    {
                      "term_id": "guest",
                      "display": "Alice"
                    },
                    {
                      "term_id": "search",
                      "display": "searches for"
                    },
                    {
                      "term_id": "room",
                      "display": "Deluxe Suite"
                    }
                  ]
                }
              ]
            }
          ],
          "source": null
        }
      ]
    }
    ```
- **when** the «Glossary» aggregations are built
- **then** the entity terms collect their «Instance»s
- **then** the verb collects its «Inflection» but not its canonical form

## ✓ «Terms» referenced by an «activity» record the «story»
`tests/unit/report/test_aggregations.py:265::test_build_glossary_aggregations_records_story_refs_via_activities` · happy-path

- **given** a «Story» whose «Activity» references an actor and a verb
- **when** the «Glossary» aggregations are built
- **then** the actor and the verb each list that «Story»

## ✓ A canonical entity reference is not an «instance»
`tests/unit/report/test_aggregations.py:336::test_build_glossary_aggregations_canonical_entity_ref_is_not_an_instance` · happy-path

- **given** a «Story» activity and a «Step» referencing entities by canonical name only
- **when** the «Glossary» aggregations are built
- **then** neither entity term records an «Instance»

## ✓ A «kindless» «term» records only its «story» ref
`tests/unit/report/test_aggregations.py:425::test_build_glossary_aggregations_kindless_term_records_only_story_ref` · happy-path

- **given** a «Kindless» «Term» referenced by a «Story» activity
- **when** the «Glossary» aggregations are built
- **then** the «Term» lists the «Story» but no «Instance» and no «Inflection»

## ✓ An «instance» seen in a fixture «step» records its fixture provenance
`tests/unit/report/test_aggregations.py:459::test_glossary_aggregations_annotates_fixture_provenance` · happy-path

- **given** a «Scenario» whose fixture-sourced «Step» names an «Instance»
- **when** the «Glossary» aggregations are built
- **then** the «Instance» carries the fixture name

## ✓ The «term» index maps each «term» to its «scenarios» once
`tests/unit/report/test_aggregations.py:553::test_build_term_scenario_index_dedups_and_includes_scenario_narration` · happy-path

- **given** a «Scenario» referencing one «Term» in two steps and another in its name
- **when** the term-scenario index is built
- **then** each «Term» maps to the scenario exactly once

## ✓ An under-anchored «activity» is flagged ineligible in rollups
`tests/unit/report/test_aggregations.py:666::test_build_story_rollups_flags_under_anchored_activity_ineligible` · happy-path

- **given** a «Story» with an anchored and an under-anchored «Activity»
- **when** the story rollups are built
- **then** only the anchored «Activity» is «Coverage»-eligible

## ✓ A «verb» «activity» ref has one identity regardless of «inflection»
`tests/unit/report/test_coverage.py:70::test_identity_of_activity_term_ref_verb_ignores_display` · happy-path

- **given** a «Verb» written canonically and as an «Inflection»
- **when** «Coverage» derives each «Term ref» identity
- **then** both collapse to the one canonical verb identity

## ✓ A branching «activity» unions references across its «paths»
`tests/unit/report/test_coverage.py:154::test_a_refs_unions_across_multi_path_activity` · happy-path

- **given** an «Activity» that branches into two «Path» alternatives
- **when** «Coverage» collects the «Activity» references
- **then** both «Instance» identities across the branches are present

## ✓ An «instance» «step» ref adds a canonical fallback
`tests/unit/report/test_coverage.py:206::test_s_for_step_instance_entity_ref_adds_canonical_fallback` · happy-path

- **given** a «Step» referring to a named «Instance»
- **when** «Coverage» computes the identity set for the «Step»
- **then** it includes the canonical «Term ref» fallback

## ✓ A «verb» ref always resolves to its canonical identity
`tests/unit/report/test_coverage.py:222::test_s_for_step_verb_ref_always_canonical` · happy-path

- **given** a «Step» using an «Inflection» of a «Verb»
- **when** «Coverage» computes its identity set
- **then** the identity ignores the surface form and stays canonical

## ✓ An unknown «term ref» is skipped
`tests/unit/report/test_coverage.py:235::test_s_for_step_unknown_term_ref_skipped` · validation

- **given** a «Step» referencing a «Term» not in the glossary
- **when** «Coverage» computes its identity set
- **then** the unknown ref contributes nothing to the identity set

## ✓ An «instance» «step» covers a canonical «activity»
`tests/unit/report/test_coverage.py:259::test_compute_coverage_covers_canonical_activity_via_instance_step` · happy-path

- **given** a «Story» with a canonical «Activity»
- **when** a «Scenario» step names a specific «Instance»
- **then** «Coverage» reports the «Activity» as covered

## ✓ A canonical «step» does not cover an «instance» «activity»
`tests/unit/report/test_coverage.py:291::test_compute_coverage_does_not_cover_instance_activity_with_canonical_step` · happy-path

- **given** an «Activity» anchored to a named «Instance»
- **when** a «Scenario» step only names the canonical «Actor»
- **then** «Coverage» leaves the more specific instance activity uncovered

## ✓ Promoting a bare word to a «verb» ref drops «coverage» from a «step» that matched
`tests/unit/report/test_coverage.py:323::test_compute_coverage_lost_when_activity_gains_a_term` · happy-path

- **given** a «Step» naming two «term refs»
- **given** the same «Activity» with that middle slot a bare word, then a «Verb» ref
- **when** «Coverage» is computed against each «Story»
- **then** the two-ref «Activity» is covered
- **then** the widened «Activity» is no longer covered

## ✓ A «scenario» «activity» binding constrains «coverage»
`tests/unit/report/test_coverage.py:372::test_compute_coverage_scenario_constrained_to_activity_ids` · happy-path

- **given** a «Story» with two matching activities
- **when** the «Scenario» «binds» only to activity 1
- **then** «Coverage» considers only the bound «Activity»

## ✓ An «activity» with two distinct «terms» is «coverage»-eligible
`tests/unit/report/test_coverage.py:419::test_is_coverage_eligible_true_for_two_distinct_terms` · happy-path

- **given** an «Activity» anchored by two distinct «Term» refs
- **when** its «Coverage» eligibility is checked
- **then** it is eligible for «Coverage» tracking

## ✓ An under-anchored «activity» is not «coverage»-eligible
`tests/unit/report/test_coverage.py:442::test_is_coverage_eligible_false_for_one_distinct_term` · happy-path

- **given** an «Activity» that mentions only one distinct «Term»
- **when** its «Coverage» eligibility is checked
- **then** it is ineligible — «Coverage» needs at least two anchors

## ✓ An under-anchored «activity» is never reported as covered
`tests/unit/report/test_coverage.py:473::test_compute_coverage_excludes_under_anchored_activity` · happy-path

- **given** a «Story» whose «Activity» is all bare words
- **when** coverage is computed against a scenario
- **then** «Coverage» excludes the under-anchored «Activity»

## ✓ Nested «steps» are walked for «coverage»
`tests/unit/report/test_coverage.py:497::test_compute_coverage_nested_steps_are_walked` · happy-path

- **given** a «Story» with one canonical «Activity»
- **when** the covering «Term ref»s live in a nested child «Step»
- **then** the nested «Step» still counts and the «Activity» is covered

## ✓ An explicit «step» binding covers an eligible «activity»
`tests/unit/report/test_coverage.py:533::test_compute_coverage_explicit_step_binding_covers_eligible_activity` · happy-path

- **given** a «Story» with a coverage-eligible «Activity»
- **when** a «Step» «binds» to it explicitly by id
- **then** «Coverage» counts it directly, without identity matching

## ✓ An explicit binding still requires eligibility
`tests/unit/report/test_coverage.py:562::test_compute_coverage_explicit_binding_ignored_for_ineligible_activity` · validation

- **given** a «Story» whose «Activity» is under-anchored
- **when** a «Step» «binds» to it explicitly by id
- **then** eligibility gates the binding, so «Coverage» stays empty

## ✓ «Parameter coloring» marks placeholders and table headers
`tests/unit/report/test_html_renderer.py:167::test_render_parametrized_step_with_structured_narration` · happy-path

- **given** a «Report» holding a «Parametrized scenario» with a «Parameter table»
- **when** the «Renderer» renders the HTML page
- **then** «Parameter coloring» classes mark the grouped placeholder and the table headers

## ✓ A passed «scenario» renders as a checked heading with «step» bullets
`tests/unit/report/test_md_renderer.py:42::test_passed_scenario_heading_and_steps` · happy-path

- **given** a «Report» holding a passed «Scenario» with three steps
  - 📎 Scenario record:
    ```
    {
      "id": "tests/t.py::test_buy",
      "narration": {
        "text": "Buy coffee",
        "parts": []
      },
      "module": "tests/t.py",
      "tags": [
        "billing",
        "happy-path"
      ],
      "status": "passed",
      "duration_ms": 0,
      "steps": [
        {
          "phase": "given",
          "narration": {
            "text": "a machine",
            "parts": []
          },
          "status": "passed",
          "children": [],
          "attachments": [],
          "error": null,
          "activity_ids": [],
          "fixture_name": null
        },
        {
          "phase": "when",
          "narration": {
            "text": "I insert $2",
            "parts": []
          },
          "status": "passed",
          "children": [],
          "attachments": [],
          "error": null,
          "activity_ids": [],
          "fixture_name": null
        },
        {
          "phase": "then",
          "narration": {
            "text": "I get a coffee",
            "parts": []
          },
          "status": "passed",
          "children": [],
          "attachments": [],
          "error": null,
          "activity_ids": [],
          "fixture_name": null
        }
      ],
      "parameters": null,
      "error": null,
      "skip_reason": null,
      "source": null,
      "story_id": null,
      "activity_ids": []
    }
    ```
- **when** the Markdown «Report» is rendered
- **then** the heading is checked and each «Step» is a phase bullet

## ✓ Nested «steps» indent under their parent
`tests/unit/report/test_md_renderer.py:142::test_nested_steps_indent` · happy-path

- **given** a «Scenario» whose when «Step» has a nested child
- **when** the Markdown «Report» is rendered
- **then** the child bullet indents under its parent

## ✓ Structured «narration» renders «terms», values and placeholders
`tests/unit/report/test_md_renderer.py:166::test_narration_parts_resolve_terms_and_values` · step-text

- **given** a «Step» whose «Narration» carries a «Term ref», a value and a placeholder
- **when** the Markdown «Report» is rendered
- **then** the «Term ref» renders in guillemets, the value verbatim and the placeholder in braces

## ✓ A «parametrized scenario» renders its «parameter table»
`tests/unit/report/test_md_renderer.py:221::test_parametrized_scenario_renders_table` · parametrization

- **given** a «Parametrized scenario» with a two-«Case» «Parameter table»
- **when** the Markdown «Report» is rendered
- **then** the heading counts the cases and the «Parameter table» lists each row

## ✓ A failing «step» is marked with a minimal error digest
`tests/unit/report/test_md_renderer.py:257::test_failing_step_is_marked_with_minimal_error` · happy-path

- **given** a failed «Scenario» whose then «Step» carries a two-line error and an internal frame
  - 📎 Error record:
    ```
    {
      "message": "ValueError: not sold out\nassert 1 == 0",
      "frames": [
        {
          "path": "/x/_pytest/runner.py",
          "lineno": 1,
          "func": "run",
          "code": "",
          "is_internal": true
        },
        {
          "path": "/x/tests/test_shop.py",
          "lineno": 88,
          "func": "test_sold_out",
          "code": "buy(m)",
          "is_internal": false
        }
      ],
      "error_tail": null
    }
    ```
- **when** the Markdown «Report» is rendered
- **then** the heading is crossed and the failed step is marked
- **then** only the first message line and the non-internal frame are quoted

## ✓ A multi-line «attachment» renders as a fenced block
`tests/unit/report/test_md_renderer.py:329::test_multiline_attachment_renders_fenced_block` · happy-path

- **given** a «Step» carrying a multi-line «Attachment»
- **when** the Markdown «Report» is rendered
- **then** the «Attachment» content sits in an indented fence, not inline

## ✓ A skipped scenario shows its skip reason
`tests/unit/report/test_md_renderer.py:450::test_skipped_scenario_shows_reason` · happy-path

- **given** a skipped «Scenario» with a reason
- **when** the Markdown «Report» is rendered
- **then** the heading is marked skipped and the reason follows the node id

## ✓ «Grouping» collapses parametrize «cases» into one «scenario»
`tests/unit/test_grouping.py:71::test_group_parametrized_any_failed_groups_as_failed` · parametrization

- **given** three «Case» records of one «Parametrized scenario»
- **when** the «grouping» pass collapses them
- **then** one scenario remains and any failed «Case» fails it

## ✓ «Term» ids are derived as URL-safe slugs · 8 cases
`tests/unit/capture/test_glossary.py:31::test_id_derive_produces_expected_slug` · happy-path

- **given** the name {text}
- **when** it is slugified into a «Term» id
- **then** the id is the expected slug {expected}

| text | expected | |
|---|---|---|
| Guest | guest | ✓ |
| Order received | order-received | ✓ |
|   Work Object   | work-object | ✓ |
| do_the_thing | do-the-thing | ✓ |
| Buy / sell | buy-sell | ✓ |
| Guest #1 | guest-1 | ✓ |
| café | caf | ✓ |
| booking system | booking-system | ✓ |

## ✓ A name with no id-able characters is rejected · 4 cases
`tests/unit/capture/test_glossary.py:58::test_id_derive_raises_on_empty_result` · validation

- **given** the name {text}
- **when** it is slugified into a «Term» id
- **then** a PytestGivenError reports the derived id is empty

| text | |
|---|---|
| --- | ✓ |
|     | ✓ |
|  | ✓ |
| ### | ✓ |

## ✓ A cross-phase «step» cannot open inside a «when_then» body · 2 cases
`tests/unit/capture/test_step_descriptor.py:355::test_when_then_rejects_cross_phase_nested_step` · validation

- **given** an «Active scenario» in a local «Collector»
- **when** a given or then opens inside the «when_then» body
- **then** a PytestGivenError reports the cross-phase nesting
- **then** the «Step stack» is left balanced

| phase_name | |
|---|---|
| given | ✓ |
| then | ✓ |

## ✓ A Template accepts bare identifiers only · 3 cases
`tests/unit/capture/test_template.py:112::test_template_non_identifier_raises_pytest_given_error` · step-text, validation

- **given** the placeholder {text}
- **when** a «Templatize» template is built from it
- **then** a PytestGivenError says bare identifiers only

| text | |
|---|---|
| count={obj.attr} | ✓ |
| {d[key]} | ✓ |
| {x + 1} | ✓ |
