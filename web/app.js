// ── Sanitización de HTML de reuniones ────────────────────────────────────────
// Elimina scripts y atributos de evento antes de inyectar contenido de minutas.
function sanitizeHtml(html) {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  tmp.querySelectorAll('script, object, embed, link[rel="import"]').forEach(el => el.remove());
  tmp.querySelectorAll('*').forEach(el => {
    [...el.attributes].forEach(attr => {
      if (/^on/i.test(attr.name) ||
          (attr.name === 'href' && /^javascript:/i.test(attr.value)) ||
          (attr.name === 'src'  && /^javascript:/i.test(attr.value))) {
        el.removeAttribute(attr.name);
      }
    });
  });
  return tmp.innerHTML;
}

// ── Estado global ────────────────────────────────────────────────────────────
let currentPath          = null;
let allMeetings          = [];
let allPending           = [];
let allProjects          = [];
let _taskData = { projects: [], tasks: [] };
let currentSidebarMode   = 'days';
let searchTimeout        = null;

// Panel de Claude
let _regenVisible        = false;

// ── Internacionalización ──────────────────────────────────────────────────────

let currentLang = localStorage.getItem('lang') || 'es';

const T = {
  es: {
    nav_notes: 'Notas', nav_action_panel: 'Acciones', nav_projects: 'Proyectos', nav_status: 'En curso', nav_trash: 'Papelera', settings_nav: 'Ajustes',
    status_idle: 'Sin actividad', pipeline_queued: 'en cola',
    step_transcribing: 'Transcribiendo', step_minutes: 'Generando minutas', step_actions: 'Generando acciones',
    rename_hint: 'Renombrar la nota', toast_renamed: 'Nota renombrada',
    rename_exists: 'Ya existe una nota con ese nombre', rename_failed: 'No se pudo renombrar',
    proj_pick_color: 'Color',
    pin: 'Fijar', unpin: 'Quitar de fijadas', pinned: 'Fijadas',
    sticky_add: 'Añadir post-it', sticky_min: 'Minimizar', sticky_del: 'Eliminar', sticky_ph: 'Escribe aquí...',
    copy_note: 'Copiar nota', copied: 'Nota copiada al portapapeles', copy_empty: 'No hay nota que copiar', copy_failed: 'No se pudo copiar',
    more_actions: 'Más acciones', export_html: 'Exportar a HTML', open_in_claude: 'Abrir en Claude', send_email: 'Enviar por email',
    tab_transcript: 'Transcripción', open_transcript_loc: 'Abrir ubicación del archivo', no_transcript_file: 'No hay transcripción disponible para esta reunión.', open_transcript_failed: 'No se pudo abrir la ubicación del archivo.',
    trash_desc: 'Las reuniones eliminadas se guardan aquí. Puedes recuperarlas o borrarlas definitivamente.',
    trash_empty: 'La papelera está vacía.',
    trash_recover: 'Recuperar', trash_delete_forever: 'Borrar definitivamente',
    trash_recovered: 'Reunión recuperada', trash_purged: 'Eliminada definitivamente',
    trash_deleted_at: 'eliminada', trash_files: 'archivos',
    trash_purge_confirm: title => `¿Borrar definitivamente "${title}"? No se podrá recuperar.`,
    lang_label: 'Idioma de la app', theme_label: 'Tema',
    n_pending: n => `${n} pendiente${n > 1 ? 's' : ''}`,
    n_done:    n => `${n} hecha${n > 1 ? 's' : ''}`,
    light: 'Claro', dark: 'Oscuro',
    manage_actions: 'Acciones pendientes',
    filter_pending: 'Pendientes', filter_done: 'Completadas',
    name_label: 'Tu nombre', name_ph: 'Nombre para filtrar acciones',
    search_ph: 'Buscar en minutas...',
    empty_title: 'Selecciona una reunión',
    empty_sub: 'Elige una reunión de la lista para ver sus minutas y acciones',
    loading: 'Cargando...', loading_meetings: 'Cargando reuniones...',
    loading_actions: 'Cargando acciones...', no_meetings: 'No hay reuniones todavía',
    tab_notes: 'Notas', tab_actions: 'Gestionar acciones', section_actions: 'Acciones',
    add_action: 'Añadir acción', toast_action_added: 'Acción añadida',
    action_title_ph: 'Descripción de la acción...', action_assignee_ph: 'Responsable (opcional)', action_deadline_ph: 'Fecha límite (opcional)',
    n_total: n => `${n} en total`,
    no_project_label: 'Sin proyecto',
    no_actions: 'No hay acciones en esta reunión',
    btn_chat: 'Chat con Claude', prompt_label: 'Prompt para Claude',
    btn_export_project: 'Exportar a proyecto', btn_export_project_title: 'Guarda transcript, notas HTML y email en la carpeta del proyecto',
    toast_export_ok: 'Exportado a la carpeta del proyecto',
    toast_export_no_project: 'Esta reunión no tiene proyecto asignado',
    toast_export_no_dir: 'El proyecto no tiene carpeta configurada (ve a Ajustes)',
    toast_export_error: 'Error al exportar al proyecto',
    btn_reenrich: 'Re-analizar', btn_reenrich_all: 'Re-analizar todas',
    toast_enriching: 'Analizando acciones...', toast_enriching_all: n => `Analizando ${n} notas...`,
    btn_execute: 'Enviar a Claude', btn_reexecute: 'Reenviar a Claude',
    btn_detail: 'Ver detalle Claude',
    btn_prompt_show: '▼ Ver prompt y editar', btn_prompt_hide: '▲ Ocultar',
    doc_file_label: 'Archivo del documento', doc_file_ph: 'Selecciona el archivo a modificar', doc_browse_file: 'Seleccionar archivo',
    confirm_dir: 'Directorio de trabajo', confirm_browse: 'Explorar',
    btn_launch: 'Lanzar', btn_launch_cancel: 'Cancelar',
    run_running: 'Corriendo', run_done: 'Hecho', run_error: 'Error', run_needs_input: 'Necesita input',
    btn_continue_terminal: 'Continuar en terminal',
    runs_panel_title: 'Ejecuciones',
    done_from_terminal: 'completado desde terminal',
    runs_fab_running: 'corriendo', runs_fab_done: 'runs',
    btn_regenerate: 'Regenerar minutas',
    regen_placeholder: 'Objetivo o contexto adicional para regenerar las minutas... ej: "El objetivo es entender mejor los conceptos de arquitectura agéntica"',
    regen_confirm: 'Regenerar',
    regen_cancel: 'Cancelar',
    toast_regenerating: 'Regenerando minutas con Claude...',
    toast_regen_done: 'Minutas regeneradas.',
    toast_regen_error: 'No se encontró la transcripción original para regenerar.',
    regen_stage_transcript_ok: 'Transcripción encontrada',
    regen_stage_generating: 'Generando minutas con Claude...',
    regen_stage_saving: 'Guardando minutas...',
    regen_stage_html: 'Exportando HTML...',
    regen_stage_actions: 'Analizando acciones...',
    regen_stage_done: '¡Completado!',
    regen_stage_error: 'Error al regenerar',
    panel_running: 'Ejecutando...', panel_done: 'Completado', panel_error: 'Error',
    panel_followup_ph: 'Añade contexto o haz una pregunta...',
    btn_done: 'Marcar hecha', btn_done_state: 'Hecha',
    btn_move_panel: 'Mover al panel', btn_in_panel: 'En panel',
    btn_go_notes: 'Ir a notas', btn_mark_complete: 'Marcar hecha',
    btn_delete: 'Eliminar', toast_deleted: 'Acción eliminada',
    confirm_delete_title: 'Eliminar proyecto',
    confirm_delete_project: name => name
      ? `¿Seguro que quieres eliminar el proyecto "${name}"? Esta acción no se puede deshacer.`
      : '¿Seguro que quieres eliminar este proyecto? Esta acción no se puede deshacer.',
    ctx_delete_meeting: 'Eliminar',
    confirm_delete_meeting_title: 'Eliminar reunión',
    confirm_delete_meeting: title => `¿Enviar la reunión "${title}" a la papelera? Podrás recuperarla desde la Papelera.`,
    toast_meeting_deleted: 'Reunión eliminada',
    no_match_actions: 'No hay acciones en el panel. Mueve acciones desde "Gestionar acciones".',
    toast_claude: 'Abriendo Claude...', toast_terminal: 'Abriendo terminal...',
    toast_outlook: 'Abriendo Outlook...', toast_done: 'Acción marcada como hecha',
    toast_moved: 'Acción movida al panel',
    pending_actions_title: 'Acciones pendientes',
    type_instruction: 'Instrucción', type_code: 'Código', type_doc: 'Documento',
    who_claude: 'Claude', who_human: 'Manual',
    no_prompt: 'Sin prompt ejecutable',
    owner_label: 'Owner', created_label: 'Creada', deadline_label: 'Deadline',
    sort_label: 'Ordenar', sort_newest: 'Más recientes', sort_oldest: 'Más antiguas',
    sort_deadline_asc: 'Deadline ↑', sort_deadline_desc: 'Deadline ↓',
    es_label: 'Español', en_label: 'English',
    name_desc: 'Se usa para identificar tus acciones asignadas',
    projects_desc: 'TeamsRecorder detecta automáticamente a qué proyecto pertenece cada reunión y permite filtrar acciones por proyecto',
    add_project: '+ Añadir proyecto',
    proj_name_ph: 'Nombre del proyecto', proj_desc_ph: 'Descripción corta', proj_stake_ph: 'emails separados por coma',
    save_btn: 'Guardar',
    recording_title: 'Grabación y Transcripción',
    whisper_desc: 'Modelo Whisper para transcribir el audio. Más grande = más preciso pero más lento. Se aplica al reiniciar.',
    open_folder_btn: 'Abrir',
    proj_dir_ph: 'Carpeta del proyecto (opcional)',
    proj_stake_label: 'Stakeholder Emails',
    proj_stake_desc: 'Estos contactos se añadirán automáticamente como destinatarios cuando envíes las minutas de una reunión de este proyecto por email. Separa varios emails con comas.',
    proj_dir_label: 'Carpeta del proyecto',
    proj_dir_desc: 'Por defecto, TeamsRecorder guarda todo en su propia carpeta. Si seleccionas aquí la carpeta raíz de tu proyecto, las acciones de Claude se ejecutarán desde ahí.',
    proj_folder_default: 'Carpeta de TeamsRecorder (por defecto)',
    proj_folder_browse: 'Seleccionar carpeta',
    proj_context_label: 'Memoria del proyecto (carpetas de contexto)',
    proj_context_desc: 'Vincula carpetas de tu PC o SharePoint (Word, PPT, PDF, Excel...). La app destila su contenido en una memoria del proyecto que da contexto y precisión a las minutas. Se actualiza sola con cada reunión.',
    proj_context_add: 'Vincular carpeta',
    mem_update: 'Actualizar memoria', mem_updating: 'Actualizando memoria del proyecto...',
    mem_updated: 'Memoria del proyecto actualizada', mem_failed: 'No se pudo actualizar la memoria',
    mem_none: 'Sin memoria todavía — vincula carpetas y pulsa "Actualizar memoria"', mem_view: 'Ver memoria',
    mem_cancelled: 'Cancelado', remove: 'Quitar',
    proj_folder_clear: 'Restablecer',
    account_settings_title: 'Cuenta',
    project_settings_title: 'Configuración de proyectos',
    no_projects: 'Sin proyectos',
    sidebar_days: 'Días', sidebar_projects: 'Proyectos',
    all_projects: 'Todos los proyectos',
    toast_model_saved: 'Modelo guardado. Reinicia para aplicar.',
    edit_btn: 'Editar', cancel_btn: 'Cancelar',
    today: 'Hoy', yesterday: 'Ayer', no_date: 'Sin fecha',
    no_minutes: 'Sin minutas disponibles',
    project_label: 'Proyecto',
    btn_detect_projects: 'Re-detectar proyectos',
    toast_detecting: 'Detectando proyectos en segundo plano…',
    toast_project_set: 'Proyecto actualizado',
    export_settings_title: 'Guardar en carpeta de proyecto',
    export_settings_desc: 'Todo se guarda siempre dentro de la app, como siempre. Además, si al crear un proyecto le asignas una carpeta, se guardarán copias de estos archivos también ahí:',
    export_settings_desc_project: 'Todo se guarda siempre en la app. Marca qué copias quieres que se guarden también en la carpeta de ESTE proyecto (requiere carpeta configurada):',
    export_needs_folder: 'Selecciona una carpeta de proyecto (con "Editar") para poder guardar copias.',
    export_html: 'Notas en HTML',
    export_email: 'Notas en formato email',
    export_transcript: 'Transcripción',
    whisper_tiny:   'tiny — Muy rápido, menor precisión',
    whisper_base:   'base — Rápido',
    whisper_small:  'small — Equilibrado',
    whisper_medium: 'medium — Buena precisión (recomendado)',
    whisper_large:  'large — Máxima precisión, más lento',
    // Task board
    task_col_name: 'Nombre de tarea', task_col_status: 'Estado',
    task_col_assignee: 'Responsable', task_col_deadline: 'Fecha límite',
    task_col_priority: 'Prioridad',
    status_not_started: 'Sin empezar', status_in_progress: 'En curso', status_done: 'Completado',
    status_blocked: 'Bloqueada', status_paused: 'En pausa', status_pending_feedback: 'Pend. feedback',
    task_col_description: 'Descripción', desc_placeholder: 'Añade una descripción...',
    proj_color_label: 'Color del proyecto',
    priority_none: '— Prioridad', priority_high: 'Alta', priority_medium: 'Media', priority_low: 'Baja',
    task_add_task: '+ Nueva tarea', task_add_subitem: '+ Nuevo subitem',
    task_new_ph: 'Nombre de la tarea…', task_empty: 'Sin tareas. Usa "+ Nueva tarea" para añadir.',
    task_no_project: 'Sin proyecto',
    modal_move_title: 'Añadir al panel', modal_project_label: 'Proyecto',
    modal_parent_label: 'Como sub-tarea de (opcional)',
    modal_parent_none: 'Tarea nueva (nivel raíz)', modal_confirm: 'Añadir al panel',
    task_from_meeting: 'de reunión',
    drawer_meeting_label: 'Reunión asociada',
    drawer_title: 'Detalle de tarea',
    pipeline_title: 'En curso',
    pipeline_idle: 'Sin actividad',
    btn_edit: 'Editar',
    edit_notes_hint: 'Edita las notas directamente y guarda. Los cambios se usarán en HTML y email.',
    notes_saved: 'Notas guardadas',
    fmt_bold: 'Negrita', fmt_italic: 'Cursiva', fmt_h2: 'Título', fmt_h3: 'Subtítulo', fmt_text: 'Texto normal', fmt_list: 'Lista',
    fmt_table: 'Tabla', table_need_cursor: 'Pon el cursor dentro de una tabla',
    tbl_insert: 'Insertar tabla', tbl_addrow: 'Añadir fila', tbl_delrow: 'Eliminar fila',
    tbl_addcol: 'Añadir columna', tbl_delcol: 'Eliminar columna', tbl_delete: 'Eliminar tabla',
    save: 'Guardar',
    cancel: 'Cancelar',
    settings_saved: 'Ajustes guardados',
    btn_delete_meeting: 'Eliminar reunión',
    btn_add_action: '+ Añadir acción',
    add_action_title_ph: 'Título de la acción...',
    add_action_assignee_ph: 'Responsable (opcional)',
    add_action_deadline_ph: 'Fecha límite (opcional, YYYY-MM-DD)',
    add_action_save: 'Guardar',
    add_action_cancel: 'Cancelar',
  },
  en: {
    nav_notes: 'Notes', nav_action_panel: 'Actions', nav_projects: 'Projects', nav_status: 'In progress', nav_trash: 'Trash', settings_nav: 'Settings',
    status_idle: 'No activity', pipeline_queued: 'queued',
    step_transcribing: 'Transcribing', step_minutes: 'Generating minutes', step_actions: 'Generating actions',
    rename_hint: 'Rename note', toast_renamed: 'Note renamed',
    rename_exists: 'A note with that name already exists', rename_failed: 'Could not rename',
    proj_pick_color: 'Color',
    pin: 'Pin', unpin: 'Unpin', pinned: 'Pinned',
    sticky_add: 'Add sticky note', sticky_min: 'Minimize', sticky_del: 'Delete', sticky_ph: 'Write here...',
    copy_note: 'Copy note', copied: 'Note copied to clipboard', copy_empty: 'Nothing to copy', copy_failed: 'Could not copy',
    more_actions: 'More actions', export_html: 'Export to HTML', open_in_claude: 'Open in Claude', send_email: 'Send by email',
    tab_transcript: 'Transcript', open_transcript_loc: 'Open file location', no_transcript_file: 'No transcript available for this meeting.', open_transcript_failed: 'Could not open the file location.',
    trash_desc: 'Deleted meetings are kept here. You can recover them or delete them permanently.',
    trash_empty: 'Trash is empty.',
    trash_recover: 'Recover', trash_delete_forever: 'Delete permanently',
    trash_recovered: 'Meeting recovered', trash_purged: 'Permanently deleted',
    trash_deleted_at: 'deleted', trash_files: 'files',
    trash_purge_confirm: title => `Permanently delete "${title}"? This cannot be undone.`,
    lang_label: 'App language', theme_label: 'Theme',
    n_pending: n => `${n} pending`,
    n_done:    n => `${n} done`,
    light: 'Light', dark: 'Dark',
    manage_actions: 'Pending actions',
    filter_pending: 'Pending', filter_done: 'Done',
    name_label: 'Your name', name_ph: 'Name to filter actions',
    search_ph: 'Search in minutes...',
    empty_title: 'Select a meeting',
    empty_sub: 'Choose a meeting from the list to view its notes and actions',
    loading: 'Loading...', loading_meetings: 'Loading meetings...',
    loading_actions: 'Loading actions...', no_meetings: 'No meetings yet',
    tab_notes: 'Notes', tab_actions: 'Manage actions', section_actions: 'Actions',
    add_action: 'Add action', toast_action_added: 'Action added',
    action_title_ph: 'Action description...', action_assignee_ph: 'Owner (optional)', action_deadline_ph: 'Deadline (optional)',
    n_total: n => `${n} total`,
    no_project_label: 'No project',
    no_actions: 'No actions in this meeting',
    btn_chat: 'Chat with Claude', prompt_label: 'Claude prompt',
    btn_export_project: 'Export to project', btn_export_project_title: 'Save transcript, HTML notes and email to the project folder',
    toast_export_ok: 'Exported to project folder',
    toast_export_no_project: 'This meeting has no project assigned',
    toast_export_no_dir: 'Project has no folder configured (go to Settings)',
    toast_export_error: 'Error exporting to project',
    btn_reenrich: 'Re-analyze', btn_reenrich_all: 'Re-analyze all',
    toast_enriching: 'Analyzing actions...', toast_enriching_all: n => `Analyzing ${n} notes...`,
    btn_execute: 'Send to Claude', btn_reexecute: 'Resend to Claude',
    btn_detail: 'View Claude detail',
    btn_prompt_show: '▼ View and edit prompt', btn_prompt_hide: '▲ Hide',
    doc_file_label: 'Document file', doc_file_ph: 'Select the file to modify', doc_browse_file: 'Select file',
    confirm_dir: 'Working directory', confirm_browse: 'Browse',
    btn_launch: 'Launch', btn_launch_cancel: 'Cancel',
    run_running: 'Running', run_done: 'Done', run_error: 'Error', run_needs_input: 'Needs input',
    btn_continue_terminal: 'Continue in terminal',
    runs_panel_title: 'Runs',
    done_from_terminal: 'completed from terminal',
    runs_fab_running: 'running', runs_fab_done: 'runs',
    btn_regenerate: 'Regenerate notes',
    regen_placeholder: 'Objective or additional context to regenerate notes... e.g. "My goal is to better understand agentic architecture concepts"',
    regen_confirm: 'Regenerate',
    regen_cancel: 'Cancel',
    toast_regenerating: 'Regenerating notes with Claude...',
    toast_regen_done: 'Notes regenerated.',
    toast_regen_error: 'Original transcript not found. Cannot regenerate.',
    regen_stage_transcript_ok: 'Transcript found',
    regen_stage_generating: 'Generating notes with Claude...',
    regen_stage_saving: 'Saving notes...',
    regen_stage_html: 'Exporting HTML...',
    regen_stage_actions: 'Analyzing actions...',
    regen_stage_done: 'Done!',
    regen_stage_error: 'Error regenerating',
    panel_running: 'Running...', panel_done: 'Done', panel_error: 'Error',
    panel_followup_ph: 'Add context or ask a question...',
    btn_done: 'Mark done', btn_done_state: 'Done',
    btn_move_panel: 'Move to panel', btn_in_panel: 'In panel',
    btn_go_notes: 'Go to notes', btn_mark_complete: 'Mark as complete',
    btn_delete: 'Delete', toast_deleted: 'Action deleted',
    confirm_delete_title: 'Delete project',
    confirm_delete_project: name => name
      ? `Are you sure you want to delete the project "${name}"? This action cannot be undone.`
      : 'Are you sure you want to delete this project? This action cannot be undone.',
    ctx_delete_meeting: 'Delete',
    confirm_delete_meeting_title: 'Delete meeting',
    confirm_delete_meeting: title => `Move the meeting "${title}" to Trash? You can recover it from the Trash.`,
    toast_meeting_deleted: 'Meeting deleted',
    no_match_actions: 'No actions in the panel. Move actions from "Manage actions".',
    toast_claude: 'Opening Claude...', toast_terminal: 'Opening terminal...',
    toast_outlook: 'Opening Outlook...', toast_done: 'Action marked as done',
    toast_moved: 'Action moved to panel',
    pending_actions_title: 'Pending actions',
    type_instruction: 'Instruction', type_code: 'Code', type_doc: 'Document',
    who_claude: 'Claude', who_human: 'Manual',
    no_prompt: 'No runnable prompt',
    owner_label: 'Owner', created_label: 'Created', deadline_label: 'Deadline',
    sort_label: 'Sort', sort_newest: 'Newest', sort_oldest: 'Oldest',
    sort_deadline_asc: 'Deadline ↑', sort_deadline_desc: 'Deadline ↓',
    es_label: 'Español', en_label: 'English',
    name_desc: 'Used to identify actions assigned to you',
    projects_desc: 'TeamsRecorder automatically detects which project each meeting belongs to and lets you filter actions by project',
    add_project: '+ Add project',
    proj_name_ph: 'Project name', proj_desc_ph: 'Short description', proj_stake_ph: 'comma-separated emails',
    save_btn: 'Save',
    recording_title: 'Recording & Transcription',
    whisper_desc: 'Whisper model for audio transcription. Larger = more accurate but slower. Takes effect after restart.',
    open_folder_btn: 'Open',
    proj_dir_ph: 'Project folder (optional)',
    proj_stake_label: 'Stakeholder Emails',
    proj_stake_desc: 'These contacts will be automatically added as recipients when you send meeting minutes for this project by email. Separate multiple emails with commas.',
    proj_dir_label: 'Project folder',
    proj_dir_desc: 'By default, TeamsRecorder saves everything in its own folder. Select your project\'s root folder here so Claude actions run from the right working directory.',
    proj_folder_default: 'TeamsRecorder folder (default)',
    proj_folder_browse: 'Browse folder',
    proj_context_label: 'Project memory (context folders)',
    proj_context_desc: 'Link folders from your PC or SharePoint (Word, PPT, PDF, Excel...). The app distills their content into a project memory that gives context and precision to the minutes. It updates automatically with each meeting.',
    proj_context_add: 'Link folder',
    mem_update: 'Update memory', mem_updating: 'Updating project memory...',
    mem_updated: 'Project memory updated', mem_failed: 'Could not update memory',
    mem_none: 'No memory yet — link folders and press "Update memory"', mem_view: 'View memory',
    mem_cancelled: 'Cancelled', remove: 'Remove',
    proj_folder_clear: 'Reset',
    account_settings_title: 'Account',
    project_settings_title: 'Project settings',
    no_projects: 'No projects yet',
    sidebar_days: 'Days', sidebar_projects: 'Projects',
    all_projects: 'All projects',
    toast_model_saved: 'Model saved. Restart to apply.',
    edit_btn: 'Edit', cancel_btn: 'Cancel',
    today: 'Today', yesterday: 'Yesterday', no_date: 'No date',
    no_minutes: 'No minutes available',
    project_label: 'Project',
    btn_detect_projects: 'Re-detect projects',
    toast_detecting: 'Detecting projects in background…',
    toast_project_set: 'Project updated',
    export_settings_title: 'Save to project folder',
    export_settings_desc: 'Everything is always saved inside the app, as usual. In addition, if you assign a folder when creating a project, copies of these files will also be saved there:',
    export_settings_desc_project: 'Everything is always saved in the app. Tick which copies you also want saved to THIS project\'s folder (requires a folder to be set):',
    export_needs_folder: 'Select a project folder (via "Edit") to enable saving copies.',
    export_html: 'HTML notes',
    export_email: 'Email-format notes',
    export_transcript: 'Transcript',
    whisper_tiny:   'tiny — Very fast, lower accuracy',
    whisper_base:   'base — Fast',
    whisper_small:  'small — Balanced',
    whisper_medium: 'medium — Good accuracy (recommended)',
    whisper_large:  'large — Best accuracy, slower',
    // Task board
    task_col_name: 'Task name', task_col_status: 'Status',
    task_col_assignee: 'Assignee', task_col_deadline: 'Deadline',
    task_col_priority: 'Priority',
    status_not_started: 'Not started', status_in_progress: 'In progress', status_done: 'Done',
    status_blocked: 'Blocked', status_paused: 'Paused', status_pending_feedback: 'Pending feedback',
    task_col_description: 'Description', desc_placeholder: 'Add a description...',
    proj_color_label: 'Project color',
    priority_none: '— Priority', priority_high: 'High', priority_medium: 'Medium', priority_low: 'Low',
    task_add_task: '+ New task', task_add_subitem: '+ New sub-item',
    task_new_ph: 'Task name…', task_empty: 'No tasks. Use "+ New task" to add one.',
    task_no_project: 'No project',
    modal_move_title: 'Add to panel', modal_project_label: 'Project',
    modal_parent_label: 'As sub-item of (optional)',
    modal_parent_none: 'New task (top level)', modal_confirm: 'Add to panel',
    task_from_meeting: 'from meeting',
    drawer_meeting_label: 'Related meeting',
    drawer_title: 'Task detail',
    pipeline_title: 'In progress',
    pipeline_idle: 'No activity',
    btn_edit: 'Edit',
    edit_notes_hint: 'Edit the notes directly and save. Changes are used for HTML and email.',
    notes_saved: 'Notes saved',
    fmt_bold: 'Bold', fmt_italic: 'Italic', fmt_h2: 'Heading', fmt_h3: 'Subheading', fmt_text: 'Normal text', fmt_list: 'List',
    fmt_table: 'Table', table_need_cursor: 'Place the cursor inside a table',
    tbl_insert: 'Insert table', tbl_addrow: 'Add row', tbl_delrow: 'Delete row',
    tbl_addcol: 'Add column', tbl_delcol: 'Delete column', tbl_delete: 'Delete table',
    save: 'Save',
    cancel: 'Cancel',
    settings_saved: 'Settings saved',
    btn_delete_meeting: 'Delete meeting',
    btn_add_action: '+ Add action',
    add_action_title_ph: 'Action title...',
    add_action_assignee_ph: 'Assignee (optional)',
    add_action_deadline_ph: 'Deadline (optional, YYYY-MM-DD)',
    add_action_save: 'Save',
    add_action_cancel: 'Cancel',
  },
};

function t(key, ...args) {
  const v = (T[currentLang] ?? T.es)[key];
  return typeof v === 'function' ? v(...args) : (v ?? key);
}

function applyLang(lang) {
  currentLang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const v = t(el.dataset.i18n);
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') el.placeholder = v;
    else el.textContent = v;
  });
  const si = document.getElementById('search-input');
  if (si) si.placeholder = t('search_ph');
  const trashBtn = document.getElementById('btn-trash');
  if (trashBtn) trashBtn.title = t('nav_trash');
  renderWhisperOptions();
  if (!document.getElementById('view-projects').classList.contains('hidden')) {
    loadProjectsSettings();
  }
}

// Mapas de rutas por índice para evitar rutas en atributos HTML
const meetingPaths  = {};   // idx -> path
const actionPaths   = {};   // i -> {path, index}

// ── Bootstrap ────────────────────────────────────────────────────────────────

window.addEventListener('pywebviewready', async () => {
  await initSettings();
  initResize();
  _initMeetingContextMenu();
  allProjects = await pywebview.api.get_projects();
  await loadMeetings();
  await refreshPendingBadge();

  // Trozo 3: detectar acciones completadas desde terminal externo
  setInterval(async () => {
    try {
      const completions = await pywebview.api.get_terminal_completions();
      for (const c of completions) {
        showToast(`${c.title ? c.title.slice(0, 60) : 'Action'} — ${t('done_from_terminal')}`);
        if (c.path && c.path === currentPath) openMeeting(currentPath);
      }
    } catch (_) {}
  }, 3000);

  // Pipeline status footer
  setInterval(updatePipelineFooter, 2000);

  // Navegación externa (evita segunda ventana cuando hay notas nuevas)
  setInterval(async () => {
    try {
      const p = await pywebview.api.get_navigate_request();
      if (p) openMeeting(p);
    } catch (_) {}
  }, 2000);
});

function _showSidebarSkeleton() {
  const list = document.getElementById('meetings-list');
  if (!list) return;
  const rows = Array.from({ length: 7 }, (_, i) =>
    `<div class="skel-item">
       <div class="skeleton skel-line skel-time"></div>
       <div class="skeleton skel-line skel-title${i % 3 === 0 ? ' short' : ''}"></div>
     </div>`).join('');
  list.innerHTML = `<div class="skel-list">${rows}</div>`;
}

async function loadMeetings() {
  _showSidebarSkeleton();
  const meetings = await pywebview.api.get_meetings();
  allMeetings = meetings;
  meetingPaths.length = 0;
  meetings.forEach((m, i) => { meetingPaths[i] = m.path; });
  renderSidebar(meetings);
  if (meetings.length > 0) openMeeting(meetings[0].path);
}

async function refreshMeetingList() {
  const meetings = await pywebview.api.get_meetings();
  allMeetings = meetings;
  meetingPaths.length = 0;
  meetings.forEach((m, i) => { meetingPaths[i] = m.path; });
  renderSidebar(meetings);
  // If the currently open meeting no longer exists, clear the right panel
  if (currentPath && !meetings.some(m => _samePath(m.path, currentPath))) {
    currentPath = null;
    document.getElementById('main-panel').innerHTML = '';
  }
}

function _samePath(a, b) {
  return a && b && a.replace(/\\/g, '/').toLowerCase() === b.replace(/\\/g, '/').toLowerCase();
}

// ── Vistas ────────────────────────────────────────────────────────────────────

function showView(view) {
  document.getElementById('view-meetings').classList.toggle('hidden', view !== 'meetings');
  document.getElementById('view-actions').classList.toggle('hidden', view !== 'actions');
  document.getElementById('view-projects').classList.toggle('hidden', view !== 'projects');
  document.getElementById('view-status').classList.toggle('hidden', view !== 'status');
  document.getElementById('view-trash').classList.toggle('hidden', view !== 'trash');
  document.getElementById('view-settings').classList.toggle('hidden', view !== 'settings');
  document.getElementById('btn-meetings').classList.toggle('active', view === 'meetings');
  document.getElementById('btn-actions').classList.toggle('active', view === 'actions');
  document.getElementById('btn-projects').classList.toggle('active', view === 'projects');
  document.getElementById('btn-status').classList.toggle('active', view === 'status');
  document.getElementById('btn-trash').classList.toggle('active', view === 'trash');
  document.getElementById('btn-settings').classList.toggle('active', view === 'settings');
  if (view === 'actions') loadTaskBoard();
  if (view === 'projects') loadProjectsSettings();
  if (view === 'trash') loadTrash();
  if (view === 'settings') loadRecordingSettings();
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function setSidebarMode(mode) {
  currentSidebarMode = mode;
  const btnDays = document.getElementById('mode-btn-days');
  const btnProj = document.getElementById('mode-btn-projects');
  if (btnDays) btnDays.classList.toggle('active', mode === 'days');
  if (btnProj) btnProj.classList.toggle('active', mode === 'projects');
  renderSidebar(allMeetings);
}

function renderSidebar(meetings) {
  if (currentSidebarMode === 'projects') {
    renderSidebarByProject(meetings);
  } else {
    renderSidebarByDays(meetings);
  }
}

const _PIN_SVG = `<svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.8a2 2 0 0 1-1.1 1.8l-1.8.9A2 2 0 0 0 5 15.2V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.8a2 2 0 0 0-1.1-1.7l-1.8-.9A2 2 0 0 1 15 10.8V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>`;

function _meetingItemHtml(m) {
  const path = meetingPaths[m.idx] || '';
  return `
    <div class="meeting-item${m.pinned ? ' pinned' : ''}" data-midx="${m.idx}">
      <div class="meeting-time">${m.time || ''}</div>
      <div class="meeting-info">
        <div class="meeting-title">${escHtml(m.title)}</div>
      </div>
      <div class="meeting-item-actions">
        <button class="btn-pin-meeting${m.pinned ? ' pinned' : ''}" data-pin-path="${escHtml(path)}" title="${m.pinned ? t('unpin') : t('pin')}">${_PIN_SVG}</button>
        <button class="btn-delete-meeting" data-del-path="${escHtml(path)}" title="${t('btn_delete_meeting')}">×</button>
      </div>
    </div>`;
}

function renderSidebarByDays(meetings) {
  const list = document.getElementById('meetings-list');
  if (!meetings.length) {
    list.innerHTML = `<div class="loading">${t('no_meetings')}</div>`;
    return;
  }

  const withIdx = meetings.map((m, idx) => ({ ...m, idx }));
  const pinned = withIdx.filter(m => m.pinned);
  const rest   = withIdx.filter(m => !m.pinned);

  const groups = {};
  rest.forEach(m => {
    const label = dayLabel(m.date);
    if (!groups[label]) groups[label] = [];
    groups[label].push(m);
  });

  let html = '';
  if (pinned.length) {
    html += `<div class="day-group"><div class="day-label pinned-label"><svg viewBox="0 0 24 24" fill="currentColor" width="11" height="11" style="vertical-align:-1px;margin-right:4px"><path d="M9 2h6a1 1 0 0 1 1 1v6l2 3v2H6v-2l2-3V3a1 1 0 0 1 1-1zm2 13h2v7h-2z"/></svg>${t('pinned')}</div>${pinned.map(_meetingItemHtml).join('')}</div>`;
  }
  html += Object.entries(groups).map(([label, items]) =>
    `<div class="day-group"><div class="day-label">${label}</div>${items.map(_meetingItemHtml).join('')}</div>`
  ).join('');
  list.innerHTML = html;

  list.querySelectorAll('.meeting-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.closest('.btn-delete-meeting') || e.target.closest('.btn-pin-meeting')) return;
      const path = meetingPaths[parseInt(el.dataset.midx)];
      if (path) openMeeting(path);
    });
    el.addEventListener('contextmenu', e => {
      const idx = parseInt(el.dataset.midx);
      const path = meetingPaths[idx];
      const title = allMeetings[idx]?.title || '';
      if (path) _showMeetingContextMenu(e, path, title, el);
    });
  });
  list.querySelectorAll('.btn-delete-meeting').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const p = btn.dataset.delPath;
      _confirmDeleteMeeting(p, (allMeetings.find(m => m.path === p) || {}).title || '', btn.closest('.meeting-item'));
    });
  });
  list.querySelectorAll('.btn-pin-meeting').forEach(btn => {
    btn.addEventListener('click', async e => {
      e.stopPropagation();
      await pywebview.api.toggle_pin(btn.dataset.pinPath);
      await refreshMeetingList();
    });
  });
}

function renderSidebarByProject(meetings) {
  const list = document.getElementById('meetings-list');
  if (!meetings.length) {
    list.innerHTML = `<div class="loading">${t('no_meetings')}</div>`;
    return;
  }

  const projNames = {};
  const projMap = {};
  allProjects.forEach(p => { projNames[p.id] = p.name; projMap[p.id] = p; });

  const groups = {};
  meetings.forEach((m, idx) => {
    const pid = m.project_id || 'none';
    if (!groups[pid]) groups[pid] = {
      name: pid === 'none' ? t('no_project_label') : (projNames[pid] || pid),
      items: [],
    };
    groups[pid].items.push({ ...m, idx });
  });

  const entries = Object.entries(groups).sort(([a], [b]) => {
    if (a === 'none') return 1;
    if (b === 'none') return -1;
    return (projNames[a] || a).localeCompare(projNames[b] || b);
  });

  list.innerHTML = entries.map(([pid, grp]) => {
    const color = _projectColor(projMap[pid] || { id: pid });
    return `
    <div class="project-sidebar-group">
      <div class="project-sidebar-header" style="border-left:2px solid ${color}" onclick="toggleProjectSidebarGroup('${escHtml(pid)}')">
        <span class="project-sidebar-name" style="color:${color}">${escHtml(grp.name)}</span>
        <span class="project-sidebar-chevron" id="pchev-${escHtml(pid)}" style="color:${color}">▾</span>
      </div>
      <div class="project-sidebar-items" id="pgroup-${escHtml(pid)}">
        ${grp.items.map(m => `
          <div class="meeting-item" data-midx="${m.idx}">
            <div class="meeting-time">${m.time || ''}</div>
            <div class="meeting-info">
              <div class="meeting-title">${escHtml(m.title)}</div>
              <div class="meeting-meta">${m.date || ''}</div>
            </div>
            <button class="btn-delete-meeting" data-del-path="${escHtml(meetingPaths[m.idx] || '')}" title="${t('btn_delete_meeting')}">×</button>
          </div>
        `).join('')}
      </div>
    </div>`;
  }).join('');

  list.querySelectorAll('.meeting-item').forEach(el => {
    el.addEventListener('click', e => {
      if (e.target.closest('.btn-delete-meeting')) return;
      const path = meetingPaths[parseInt(el.dataset.midx)];
      if (path) openMeeting(path);
    });
    el.addEventListener('contextmenu', e => {
      const idx = parseInt(el.dataset.midx);
      const path = meetingPaths[idx];
      const title = allMeetings[idx]?.title || '';
      if (path) _showMeetingContextMenu(e, path, title, el);
    });
  });
  list.querySelectorAll('.btn-delete-meeting').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const p = btn.dataset.delPath;
      _confirmDeleteMeeting(p, (allMeetings.find(m => m.path === p) || {}).title || '', btn.closest('.meeting-item'));
    });
  });
}

// ── Papelera (reuniones eliminadas) ──────────────────────────────────────────

async function loadTrash() {
  const list = document.getElementById('trash-list');
  if (!list) return;
  list.innerHTML = `<div class="loading">${t('loading')}</div>`;
  let items = [];
  try { items = await pywebview.api.list_trash(); } catch (_) {}
  if (!items || !items.length) {
    list.innerHTML = `<div style="color:var(--muted);font-size:13px">${t('trash_empty')}</div>`;
    return;
  }
  list.innerHTML = items.map(it => {
    const id = escHtml(it.id);
    const title = escHtml(it.title || it.stem || '');
    const when = (it.deleted_at || '').slice(0, 10);
    return `
    <div class="trash-item" data-trash-id="${id}">
      <div class="trash-item-info">
        <div class="trash-item-title">${title}</div>
        <div class="trash-item-meta">${escHtml(it.date || '')} · ${t('trash_deleted_at')} ${escHtml(when)} · ${it.file_count || 0} ${t('trash_files')}</div>
      </div>
      <div class="trash-item-actions">
        <button class="btn btn-primary btn-sm" onclick="recoverMeeting('${id}')">${t('trash_recover')}</button>
        <button class="btn btn-delete btn-sm" onclick="purgeTrashMeeting('${id}', '${title}')">${t('trash_delete_forever')}</button>
      </div>
    </div>`;
  }).join('');
}

async function recoverMeeting(id) {
  const ok = await pywebview.api.recover_meeting(id);
  if (ok) {
    showToast(t('trash_recovered'));
    await loadTrash();
    try { if (typeof refreshMeetingList === 'function') await refreshMeetingList(); } catch (_) {}
  }
}

function purgeTrashMeeting(id, title) {
  openConfirmModal(
    t('trash_purge_confirm', title || ''),
    async () => {
      const ok = await pywebview.api.purge_trash_meeting(id);
      if (ok) { showToast(t('trash_purged')); await loadTrash(); }
    },
    { title: t('trash_delete_forever'), okLabel: t('btn_delete') }
  );
}

function toggleProjectSidebarGroup(pid) {
  const items = document.getElementById('pgroup-' + pid);
  const chev  = document.getElementById('pchev-' + pid);
  if (!items) return;
  items.classList.toggle('collapsed');
  if (chev) chev.textContent = items.classList.contains('collapsed') ? '▸' : '▾';
}

// ── Meeting context menu (right-click: rename / delete) ──────────────────────

let _ctxPath  = null;
let _ctxTitle = null;
let _ctxEl    = null;

function _initMeetingContextMenu() {
  const menu   = document.getElementById('meeting-ctx-menu');
  const delBtn = document.getElementById('ctx-delete-btn');
  if (!menu) return;

  delBtn.onclick = () => { menu.classList.add('hidden'); _confirmDeleteMeeting(_ctxPath, _ctxTitle, _ctxEl); };

  document.addEventListener('click', () => menu.classList.add('hidden'));
  document.addEventListener('contextmenu', e => {
    if (!e.target.closest('.meeting-item')) menu.classList.add('hidden');
  });

// Cerrar el menú de tabla del editor al hacer clic fuera
document.addEventListener('click', (e) => {
  const menu = document.getElementById('table-menu');
  if (menu && !menu.classList.contains('hidden')) {
    if (!e.target.closest || !e.target.closest('.notes-tool-dropdown')) {
      menu.classList.add('hidden');
    }
  }
});
}

// ── Renombrar título de la nota ──────────────────────────────────────────────

let _renamingMeeting = false;

function startRenameMeeting() {
  if (_renamingMeeting || !currentPath) return;
  const el = document.getElementById('detail-title');
  if (!el) return;
  _renamingMeeting = true;

  const current = el.textContent;
  const input = document.createElement('input');
  input.className = 'detail-title-input';
  input.value = current;
  input.maxLength = 80;
  el.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const finish = async (save) => {
    if (done) return;
    done = true;
    _renamingMeeting = false;
    const newTitle = input.value.trim();
    if (save && newTitle && newTitle !== current) {
      const res = await pywebview.api.rename_meeting(currentPath, newTitle);
      if (res && res.ok) {
        currentPath = res.path;
        showToast(t('toast_renamed'));
        await loadMeetings();
        await openMeeting(res.path);
        return;
      }
      const msg = (res && res.error === 'exists') ? t('rename_exists') : t('rename_failed');
      showToast(msg);
    }
    // Restaurar sin cambios
    if (currentPath) await openMeeting(currentPath);
  };

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter')      { e.preventDefault(); finish(true); }
    else if (e.key === 'Escape'){ e.preventDefault(); finish(false); }
  });
  input.addEventListener('blur', () => finish(true));
}

// ── Transcripción ────────────────────────────────────────────────────────────
let _transcriptPath = '';

async function _loadTranscript(path) {
  const body = document.getElementById('transcript-body');
  const btn = document.getElementById('btn-open-transcript');
  if (!body) return;
  let res;
  try { res = await pywebview.api.get_transcript(path); } catch (_) { res = null; }
  if (res && res.text) {
    body.textContent = res.text;
    _transcriptPath = res.path || '';
    if (btn) btn.style.display = _transcriptPath ? '' : 'none';
  } else {
    body.innerHTML = `<em>${t('no_transcript_file')}</em>`;
    _transcriptPath = '';
    if (btn) btn.style.display = 'none';
  }
}

async function openTranscriptLocation() {
  if (!_transcriptPath) return;
  let ok = false;
  try { ok = await pywebview.api.reveal_in_explorer(_transcriptPath); } catch (_) {}
  if (!ok) showToast(t('open_transcript_failed'));
}

// ── Copiar nota ──────────────────────────────────────────────────────────────

function copyNote() {
  const el = document.querySelector('#section-notes .minutes-content');
  if (!el) { showToast(t('copy_empty')); return; }
  const html = el.innerHTML;
  const text = el.innerText.trim();
  if (!text) { showToast(t('copy_empty')); return; }
  const done = () => showToast(t('copied'));

  // Fallback enriquecido: selecciona el HTML y copia con execCommand
  // (mantiene tablas y formato al pegar en Word/Outlook/OneNote; funciona en file://)
  const richFallback = () => {
    const div = document.createElement('div');
    div.contentEditable = 'true';
    div.innerHTML = html;
    div.style.cssText = 'position:fixed;left:-9999px;top:0;opacity:0';
    document.body.appendChild(div);
    const range = document.createRange();
    range.selectNodeContents(div);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (_) {}
    sel.removeAllRanges();
    div.remove();
    if (ok) done();
    else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, () => showToast(t('copy_failed')));
    } else { showToast(t('copy_failed')); }
  };

  // Preferente: Clipboard API con HTML + texto plano (pegado rico o plano según destino)
  if (navigator.clipboard && window.ClipboardItem) {
    try {
      const item = new ClipboardItem({
        'text/html':  new Blob([html], { type: 'text/html' }),
        'text/plain': new Blob([text], { type: 'text/plain' }),
      });
      navigator.clipboard.write([item]).then(done, richFallback);
    } catch (_) { richFallback(); }
  } else {
    richFallback();
  }
}

// ── Sticky notes (post-its) ──────────────────────────────────────────────────
let _stickies = [];
let _stickySaveTimer = null;

async function _loadStickies(path) {
  const layer = document.getElementById('sticky-layer');
  if (!layer) return;
  try { _stickies = (await pywebview.api.get_stickies(path)) || []; }
  catch (_) { _stickies = []; }
  layer.innerHTML = _stickies.map(_stickyHtml).join('');
  _wireStickies();
}

function _stickyPreview(text) {
  return escHtml((text || '').split('\n')[0].slice(0, 26));
}

function _stickyHtml(s) {
  return `
    <div class="sticky-note${s.minimized ? ' min' : ''}" data-sid="${escHtml(s.id)}">
      <div class="sticky-head">
        <span class="sticky-preview">${_stickyPreview(s.text)}</span>
        <button class="sticky-btn sticky-min" title="${t('sticky_min')}">${s.minimized ? '+' : '–'}</button>
        <button class="sticky-btn sticky-del" title="${t('sticky_del')}">×</button>
      </div>
      <textarea class="sticky-body" placeholder="${t('sticky_ph')}" spellcheck="false">${escHtml(s.text || '')}</textarea>
    </div>`;
}

function _wireStickies() {
  const layer = document.getElementById('sticky-layer');
  if (!layer) return;
  layer.querySelectorAll('.sticky-note').forEach(node => {
    const id = node.dataset.sid;
    const ta = node.querySelector('.sticky-body');
    node.querySelector('.sticky-del').onclick = () => {
      _stickies = _stickies.filter(x => x.id !== id);
      node.remove();
      _saveStickies();
    };
    node.querySelector('.sticky-min').onclick = (e) => {
      const s = _stickies.find(x => x.id === id);
      if (!s) return;
      s.minimized = !s.minimized;
      node.classList.toggle('min', s.minimized);
      e.currentTarget.textContent = s.minimized ? '+' : '–';
      const prev = node.querySelector('.sticky-preview');
      if (prev) prev.textContent = (ta.value || '').split('\n')[0].slice(0, 26);
      _saveStickies();
    };
    ta.oninput = () => {
      const s = _stickies.find(x => x.id === id);
      if (s) s.text = ta.value;
      _saveStickies();
    };
  });
}

function addSticky() {
  if (!currentPath) return;
  const layer = document.getElementById('sticky-layer');
  if (!layer) return;
  const s = { id: 'st' + Date.now(), text: '', minimized: false };
  _stickies.push(s);
  layer.insertAdjacentHTML('beforeend', _stickyHtml(s));
  _wireStickies();
  _saveStickies();
  const ta = layer.querySelector(`.sticky-note[data-sid="${s.id}"] .sticky-body`);
  if (ta) ta.focus();
}

function _saveStickies() {
  clearTimeout(_stickySaveTimer);
  const path = currentPath;
  const snapshot = JSON.parse(JSON.stringify(_stickies));
  _stickySaveTimer = setTimeout(() => {
    try { pywebview.api.save_stickies(path, snapshot); } catch (_) {}
  }, 400);
}

function _showMeetingContextMenu(e, path, title, el) {
  e.preventDefault();
  e.stopPropagation();
  _ctxPath  = path;
  _ctxTitle = title;
  _ctxEl    = el;
  const menu = document.getElementById('meeting-ctx-menu');
  menu.classList.remove('hidden');
  const x = Math.min(e.clientX, window.innerWidth  - 175);
  const y = Math.min(e.clientY, window.innerHeight - 75);
  menu.style.left = x + 'px';
  menu.style.top  = y + 'px';
}


function _confirmDeleteMeeting(pathToDelete, titleToDelete, elToRemove) {
  if (!pathToDelete) return;

  openConfirmModal(
    t('confirm_delete_meeting', titleToDelete || ''),
    async () => {
      const ok = await pywebview.api.delete_meeting(pathToDelete);
      if (ok) {
        showToast(t('toast_meeting_deleted'));

        // Clear right panel immediately if this meeting is open
        if (_samePath(currentPath, pathToDelete)) {
          currentPath = null;
          document.getElementById('main-panel').innerHTML = '';
        }

        // Remove sidebar item immediately for instant feedback
        if (elToRemove && elToRemove.isConnected) {
          const dayGroup  = elToRemove.closest('.day-group');
          const projGroup = elToRemove.closest('.project-sidebar-group');
          elToRemove.remove();
          if (dayGroup  && !dayGroup.querySelector('.meeting-item'))  dayGroup.remove();
          if (projGroup && !projGroup.querySelector('.meeting-item')) projGroup.remove();
        }

        // Full refresh — also clears right panel if currentPath is gone
        await refreshMeetingList();
      }
    },
    { title: t('confirm_delete_meeting_title'), okLabel: t('btn_delete') }
  );
}

function dayLabel(dateStr) {
  if (!dateStr) return t('no_date');
  const [y, mo, d] = dateStr.split('-').map(Number);
  const date  = new Date(y, mo - 1, d);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diff  = Math.round((today - date) / 86400000);
  const locale = currentLang === 'es' ? 'es-ES' : 'en-US';
  if (diff === 0) return t('today');
  if (diff === 1) return t('yesterday');
  if (diff < 7)   return date.toLocaleDateString(locale, { weekday: 'long' });
  return date.toLocaleDateString(locale, { day: 'numeric', month: 'long' });
}

// ── Apertura de reunión ───────────────────────────────────────────────────────

async function openMeeting(path) {
  currentPath = path;
  _regenVisible = false;

  document.querySelectorAll('.meeting-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.meeting-item').forEach(el => {
    const idx = parseInt(el.dataset.midx);
    if (meetingPaths[idx] === path) el.classList.add('active');
  });

  const panel = document.getElementById('main-panel');
  panel.innerHTML = `<div class="loading">${t('loading')}</div>`;

  const [minutesHtml, actions] = await Promise.all([
    pywebview.api.get_minutes_html(path),
    pywebview.api.get_actions(path),
  ]);

  const meeting = allMeetings.find(m => m.path === path) || {};
  const pendingCount = actions ? actions.filter(a => !a.executed).length : 0;
  const curProjId = meeting.project_id || '';
  const projOptions = [
    `<option value="">${t('no_project_label')}</option>`,
    ...allProjects.map(p =>
      `<option value="${escHtml(p.id)}"${curProjId === p.id ? ' selected' : ''}>${escHtml(p.name)}</option>`
    ),
  ].join('');

  panel.innerHTML = `
    <div class="meeting-detail">
      <div class="sticky-layer" id="sticky-layer"></div>
      <div class="detail-header">
        <div>
          <div class="detail-title-row">
            <div class="detail-title" id="detail-title" title="${t('rename_hint')}" ondblclick="startRenameMeeting()">${escHtml(meeting.title || t('empty_title'))}</div>
            <button class="detail-title-edit" title="${t('rename_hint')}" onclick="startRenameMeeting()"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
          </div>
          <div class="detail-meta">
            <span>${meeting.date || ''} ${meeting.time || ''}</span>
            <span class="detail-project-wrap">
              <label class="detail-project-label">${t('project_label')}</label>
              <select class="detail-project-select" id="meeting-project-select" onchange="onMeetingProjectChange(this.value)">${projOptions}</select>
            </span>
          </div>
        </div>
        <div class="detail-actions-bar">
          <button class="action-icon-btn" id="btn-edit-notes" title="${t('btn_edit')}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg></button>
          <button class="action-icon-btn" id="btn-copy" title="${t('copy_note')}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button>
          <button class="action-icon-btn action-icon-btn--primary" id="btn-email" title="${t('send_email')}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/></svg></button>
          <div class="action-more-wrap">
            <button class="action-icon-btn" id="btn-more" title="${t('more_actions')}"><svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg></button>
            <div class="action-menu hidden" id="action-menu">
              <button class="action-menu-item" id="btn-sticky"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M15 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h9l7-7V5a2 2 0 0 0-2-2z"/><path d="M14 21v-6a1 1 0 0 1 1-1h6"/></svg><span>${t('sticky_add')}</span></button>
              <button class="action-menu-item" id="btn-regenerate"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74"/><path d="M3 3v4h4"/></svg><span>${t('btn_regenerate')}</span></button>
              <button class="action-menu-item" id="btn-html"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg><span>${t('export_html')}</span></button>
              <button class="action-menu-item" id="btn-claude"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M8 12h8M8 8h8M8 16h5"/><rect x="3" y="3" width="18" height="18" rx="2"/></svg><span>${t('open_in_claude')}</span></button>
            </div>
          </div>
        </div>
      </div>
      <div class="regen-bar hidden" id="regen-bar">
        <textarea id="regen-textarea" rows="2" placeholder="${t('regen_placeholder')}"></textarea>
        <div class="regen-bar-btns">
          <button class="btn btn-primary btn-sm" id="btn-regen-confirm">${t('regen_confirm')}</button>
          <button class="btn btn-ghost btn-sm" id="btn-regen-cancel">${t('regen_cancel')}</button>
        </div>
      </div>
      <div class="detail-tabs">
        <button class="detail-tab active" id="tab-notes" data-tab="notes">${t('tab_notes')}</button>
        <button class="detail-tab" id="tab-actions" data-tab="actions">
          ${t('tab_actions')} ${pendingCount > 0 ? `<span class="tab-badge">${pendingCount}</span>` : ''}
        </button>
        <button class="detail-tab" id="tab-transcript" data-tab="transcript">${t('tab_transcript')}</button>
      </div>
      <div class="minutes-section" id="section-notes">
        <div class="minutes-content">${minutesHtml ? sanitizeHtml(minutesHtml) : `<em>${t('no_minutes')}</em>`}</div>
      </div>
      <div class="actions-section hidden" id="section-actions">
        <div class="actions-section-header">
          <div class="section-label">${t('section_actions')}</div>
          <div class="actions-count">${t('n_total', actions ? actions.length : 0)}</div>
          <button class="btn btn-ghost btn-sm" id="btn-add-action" style="margin-left:auto">+ ${t('add_action')}</button>
        </div>
        <div id="add-action-form" class="add-action-form" style="display:none"></div>
        <div id="meeting-actions"></div>
      </div>
      <div class="transcript-section hidden" id="section-transcript">
        <div class="transcript-header">
          <div class="section-label">${t('tab_transcript')}</div>
          <button class="btn btn-ghost btn-sm" id="btn-open-transcript" style="margin-left:auto;display:none"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7a2 2 0 0 1 2-2h3.5l2 2H18a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z"/></svg>${t('open_transcript_loc')}</button>
        </div>
        <div class="transcript-body" id="transcript-body"><div class="loading">${t('loading')}</div></div>
      </div>
    </div>`;

  document.getElementById('btn-email').addEventListener('click', () => sendEmail(path));
  document.getElementById('btn-html').addEventListener('click', () => openHtml(path));
  document.getElementById('btn-claude').addEventListener('click', () => openMinutesInClaude(path));
  document.getElementById('btn-regenerate').addEventListener('click', () => toggleRegenBar());
  document.getElementById('btn-regen-cancel').addEventListener('click', () => toggleRegenBar(false));
  document.getElementById('btn-regen-confirm').addEventListener('click', () => confirmRegen(path));
  document.getElementById('btn-edit-notes').addEventListener('click', () => toggleEditNotes(path));
  document.getElementById('btn-sticky').addEventListener('click', () => addSticky());
  document.getElementById('btn-copy').addEventListener('click', () => copyNote());
  // Menú "más acciones" (overflow)
  const _moreBtn = document.getElementById('btn-more');
  const _actionMenu = document.getElementById('action-menu');
  if (_moreBtn && _actionMenu) {
    _moreBtn.addEventListener('click', () => _actionMenu.classList.toggle('hidden'));
    _actionMenu.querySelectorAll('.action-menu-item').forEach(item =>
      item.addEventListener('click', () => _actionMenu.classList.add('hidden')));
  }
  _loadStickies(path);


  requestAnimationFrame(() => {
    const header = panel.querySelector('.detail-header');
    const tabs   = panel.querySelector('.detail-tabs');
    if (header && tabs) tabs.style.top = header.offsetHeight + 'px';
  });

  // Tabs: sub-pantallas exclusivas
  document.querySelectorAll('.detail-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const which = tab.dataset.tab;
      document.getElementById('section-notes').classList.toggle('hidden', which !== 'notes');
      document.getElementById('section-actions').classList.toggle('hidden', which !== 'actions');
      const tsec = document.getElementById('section-transcript');
      if (tsec) tsec.classList.toggle('hidden', which !== 'transcript');
      panel.scrollTo({ top: 0, behavior: 'smooth' });
      if (which === 'transcript') _loadTranscript(path);
    });
  });
  document.getElementById('btn-open-transcript')?.addEventListener('click', () => openTranscriptLocation());

  document.getElementById('btn-add-action')?.addEventListener('click', () => toggleAddActionForm(path));

  const actionsDiv = document.getElementById('meeting-actions');
  if (actions && actions.length) {
    renderActionCards(actions, path, actionsDiv, meeting.date || '');
    _prefillWorkingDirs(actions, path);
  } else {
    actionsDiv.innerHTML = `<div style="color:var(--muted);font-size:13px;margin-bottom:10px">${t('no_actions')}</div>`;
  }
  _renderAddActionBtn(path, actionsDiv);
}

// ── Añadir acción manual a una reunión ────────────────────────────────────────

function toggleAddActionForm(path) {
  const form = document.getElementById('add-action-form');
  if (!form) return;
  if (form.style.display !== 'none') { form.style.display = 'none'; form.innerHTML = ''; return; }
  form.style.display = 'block';
  form.innerHTML = `
    <input type="text" id="new-action-title" class="settings-text-input" placeholder="${t('action_title_ph')}">
    <div class="add-action-row">
      <input type="text" id="new-action-assignee" class="settings-text-input" placeholder="${t('action_assignee_ph')}">
      <input type="text" id="new-action-deadline" class="settings-text-input" placeholder="${t('action_deadline_ph')}">
    </div>
    <div class="add-action-btns">
      <button class="btn btn-primary btn-sm" id="new-action-save">${t('save_btn')}</button>
      <button class="btn btn-ghost btn-sm" id="new-action-cancel">${t('regen_cancel')}</button>
    </div>`;
  const titleEl = document.getElementById('new-action-title');
  titleEl.focus();
  const close = () => { form.style.display = 'none'; form.innerHTML = ''; };
  document.getElementById('new-action-cancel').onclick = close;
  const save = async () => {
    const title = titleEl.value.trim();
    if (!title) { titleEl.focus(); return; }
    const assignee = document.getElementById('new-action-assignee').value.trim();
    const deadline = document.getElementById('new-action-deadline').value.trim();
    const ok = await pywebview.api.add_meeting_action(path, title, deadline, assignee);
    if (ok) {
      close();
      await refreshMeetingActions(path);
      showToast(t('toast_action_added'));
    }
  };
  document.getElementById('new-action-save').onclick = save;
  titleEl.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
}

async function refreshMeetingActions(path) {
  const actions = await pywebview.api.get_actions(path);
  const actionsDiv = document.getElementById('meeting-actions');
  if (!actionsDiv) return;
  const countEl = document.querySelector('#section-actions .actions-count');
  if (countEl) countEl.textContent = t('n_total', actions ? actions.length : 0);
  if (actions && actions.length) {
    renderActionCards(actions, path, actionsDiv, '');
    _prefillWorkingDirs(actions, path);
  } else {
    actionsDiv.innerHTML = `<div style="color:var(--muted);font-size:13px">${t('no_actions')}</div>`;
  }
  try { refreshPendingBadge(); } catch (_) {}
}

// ── Meta row compartida (Owner · Creada · Deadline · badge) ──────────────────

function actionMetaHtml(a, meetingDate, claudeExec) {
  if (claudeExec === undefined) {
    claudeExec = a.claude_executable ?? (a.type && a.type !== 'human');
  }
  const owner    = a.assignee || '—';
  const created  = a.created_at || meetingDate || '—';
  const dlHtml   = a.deadline
    ? `<span class="deadline-badge">${escHtml(a.deadline)}</span>`
    : '<span class="meta-value-empty">—</span>';
  return `<div class="action-meta">
    <span class="meta-label">${t('owner_label')}:</span><span class="action-assignee">${escHtml(owner)}</span>
    <span class="meta-sep">·</span>
    <span class="meta-label">${t('created_label')}:</span><span class="meta-value">${escHtml(created)}</span>
    <span class="meta-sep">·</span>
    <span class="meta-label">${t('deadline_label')}:</span>${dlHtml}
    <span class="${claudeExec ? 'auto-run-badge' : 'manual-badge'}">${claudeExec ? t('who_claude') : t('who_human')}</span>
  </div>`;
}

// ── Tarjetas de acciones (vista Notas) ────────────────────────────────────────

function renderActionCards(actions, path, container, meetingDate) {
  container.innerHTML = actions.map(a => {
    const prompt = a.prompt_enriched || a.prompt_original || '';
    const claudeExec = a.claude_executable || (a.type && a.type !== 'human' && prompt.trim().length > 0);
    const inPanel = a.in_panel === true;
    const autoOpen = false;
    return `
    <div class="action-card ${a.executed ? 'done' : ''}" id="card-${a.index}">
      <div class="action-card-row">
        <div class="action-card-main">
          <span class="action-title ${a.executed ? 'done-text' : ''}">${escHtml(a.title)}</span>
          ${actionMetaHtml(a, meetingDate, claudeExec)}
        </div>
        <div class="action-card-btns">
          <button class="btn btn-ghost btn-sm${inPanel ? ' btn-in-panel' : ''}" data-panel="${a.index}" ${inPanel ? 'disabled' : ''}>
            ${inPanel ? t('btn_in_panel') : t('btn_move_panel')}
          </button>
          ${claudeExec
            ? `<button class="btn btn-ghost btn-sm" data-toggle="${a.index}">${autoOpen ? t('btn_prompt_hide') : t('btn_prompt_show')}</button>`
            : ''}
          <button class="btn btn-delete btn-sm" data-del="${a.index}" title="${t('btn_delete')}">×</button>
        </div>
      </div>
      ${claudeExec ? `
      <div class="action-card-body ${autoOpen ? 'open' : ''}" id="body-${a.index}">
        ${a.type === 'document_change' ? `
        <div class="prompt-label">${t('doc_file_label')}</div>
        <div class="dir-row">
          <input type="text" class="dir-input" id="dir-${a.index}" placeholder="${escHtml(a.archivo || t('doc_file_ph'))}">
          <button class="btn btn-ghost btn-sm" data-browse-file="${a.index}">${t('doc_browse_file')}</button>
        </div>` : `
        <div class="prompt-label">${t('confirm_dir')}</div>
        <div class="dir-row">
          <input type="text" class="dir-input" id="dir-${a.index}" placeholder="${t('confirm_dir')}">
          <button class="btn btn-ghost btn-sm" data-browse="${a.index}">${t('confirm_browse')}</button>
        </div>`}
        <div class="dir-hint" id="dirhint-${a.index}"></div>
        <div class="prompt-label">${t('prompt_label')}</div>
        <textarea class="prompt-box" id="prompt-${a.index}">${escHtml(prompt)}</textarea>
        <div class="action-btn-row">
          <button class="btn btn-primary btn-sm" data-launch="${a.index}" ${a.executed ? 'disabled' : ''}>${t('btn_launch')}</button>
          <button class="btn btn-ghost btn-sm" data-toggleclose="${a.index}">${t('btn_launch_cancel')}</button>
        </div>
      </div>` : ''}
    </div>`;
  }).join('');

  container.querySelectorAll('[data-del]').forEach(el => {
    el.addEventListener('click', () => deleteAction(path, parseInt(el.dataset.del), el));
  });
  container.querySelectorAll('[data-panel]').forEach(el => {
    el.addEventListener('click', () => moveToPanel(path, parseInt(el.dataset.panel), el));
  });
  container.querySelectorAll('[data-toggle]').forEach(el => {
    el.addEventListener('click', () => toggleCard(parseInt(el.dataset.toggle), path));
  });
  container.querySelectorAll('[data-toggleclose]').forEach(el => {
    el.addEventListener('click', () => toggleCard(parseInt(el.dataset.toggleclose), path));
  });
  container.querySelectorAll('[data-browse]').forEach(el => {
    el.addEventListener('click', () => browseRunDir(parseInt(el.dataset.browse)));
  });
  container.querySelectorAll('[data-browse-file]').forEach(el => {
    el.addEventListener('click', () => browseRunFile(parseInt(el.dataset.browseFile)));
  });
  container.querySelectorAll('[data-launch]').forEach(el => {
    el.addEventListener('click', () => launchRun(path, parseInt(el.dataset.launch)));
  });

  container.querySelectorAll('.prompt-box').forEach(el => {
    el.addEventListener('blur', () => savePrompt(path, parseInt(el.id.replace('prompt-', '')), el.value));
  });
}

function _renderAddActionBtn(path, container) {
  const wrapper = document.createElement('div');
  wrapper.style.cssText = 'margin-top:10px';
  const btn = document.createElement('button');
  btn.className = 'btn btn-ghost btn-sm';
  btn.textContent = t('btn_add_action');
  btn.addEventListener('click', () => showAddActionForm(path, container, wrapper));
  wrapper.appendChild(btn);
  container.appendChild(wrapper);
}

function showAddActionForm(path, container, btnWrapper) {
  btnWrapper.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:6px;padding:10px;background:var(--card);border-radius:8px;margin-top:4px">
      <input type="text" id="new-action-title" class="dir-input" placeholder="${escHtml(t('add_action_title_ph'))}" style="font-size:13px">
      <input type="text" id="new-action-assignee" class="dir-input" placeholder="${escHtml(t('add_action_assignee_ph'))}" style="font-size:13px">
      <input type="text" id="new-action-deadline" class="dir-input" placeholder="${escHtml(t('add_action_deadline_ph'))}" style="font-size:13px">
      <div style="display:flex;gap:8px;margin-top:2px">
        <button class="btn btn-primary btn-sm" id="btn-save-action">${t('add_action_save')}</button>
        <button class="btn btn-ghost btn-sm" id="btn-cancel-action">${t('add_action_cancel')}</button>
      </div>
    </div>`;

  document.getElementById('new-action-title').focus();

  document.getElementById('btn-cancel-action').addEventListener('click', () => {
    btnWrapper.innerHTML = '';
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost btn-sm';
    btn.textContent = t('btn_add_action');
    btn.addEventListener('click', () => showAddActionForm(path, container, btnWrapper));
    btnWrapper.appendChild(btn);
  });

  document.getElementById('btn-save-action').addEventListener('click', async () => {
    const title = document.getElementById('new-action-title').value.trim();
    if (!title) { document.getElementById('new-action-title').focus(); return; }
    const assignee = document.getElementById('new-action-assignee').value.trim();
    const deadline = document.getElementById('new-action-deadline').value.trim();
    const action = await pywebview.api.create_action(path, title, assignee, deadline);
    if (action && action.index !== undefined) {
      const actions = await pywebview.api.get_actions(path);
      renderActionCards(actions, path, container, '');
      _prefillWorkingDirs(actions, path);
      _renderAddActionBtn(path, container);
    }
  });
}

async function toggleCard(index, path) {
  const body = document.getElementById('body-' + index);
  if (!body) return;
  const wasOpen = body.classList.contains('open');
  body.classList.toggle('open');
  const btn = document.querySelector(`[data-toggle="${index}"]`);
  if (btn) btn.textContent = wasOpen ? t('btn_prompt_show') : t('btn_prompt_hide');
  if (!wasOpen && path) {
    const dirInput = document.getElementById('dir-' + index);
    if (dirInput && !dirInput.value) {
      const suggested = await pywebview.api.get_action_working_dir(path, index);
      if (suggested) {
        dirInput.value = suggested;
        _showDirHint(index, suggested);
      }
    }
  }
}

function _showDirHint(index, path) {
  const el = document.getElementById('dirhint-' + index);
  if (!el) return;
  if (!path) { el.textContent = ''; el.className = 'dir-hint'; return; }
  const isFile = /\.[a-zA-Z0-9]{1,5}$/.test(path.split(/[\\/]/).pop());
  if (isFile) {
    el.textContent = 'Claude modificará este archivo directamente';
    el.className = 'dir-hint dir-hint-ok';
  } else if (path.toLowerCase().includes('teamsrecorder')) {
    el.textContent = 'Ajusta la carpeta si el documento está en otro directorio';
    el.className = 'dir-hint dir-hint-warn';
  } else {
    el.textContent = '';
    el.className = 'dir-hint';
  }
}

async function _prefillWorkingDirs(actions, path) {
  for (const a of actions) {
    if (!a.executed && a.claude_executable) {
      const hintEl = document.getElementById('dirhint-' + a.index);
      if (a.type === 'document_change') {
        // Document actions need a specific file — prompt user to select it
        if (hintEl) {
          hintEl.textContent = 'Selecciona el archivo concreto con el botón de la derecha';
          hintEl.className = 'dir-hint dir-hint-warn';
        }
      } else {
        const dirEl = document.getElementById('dir-' + a.index);
        if (dirEl && !dirEl.value) {
          const suggested = await pywebview.api.get_action_working_dir(path, a.index);
          if (suggested) {
            dirEl.value = suggested;
            _showDirHint(a.index, suggested);
          }
        }
      }
    }
  }
}

// ── Task board (Panel de Acciones — Notion style) ────────────────────────────

const PROJECT_COLORS = ['#6366f1','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#ec4899','#84cc16','#14b8a6'];

function _projectColor(project) {
  if (!project || project.id === 'none') return 'var(--accent)';
  if (project.color) return project.color;
  const id = project.id || '';
  let hash = 0;
  for (let i = 0; i < id.length; i++) hash = (hash + id.charCodeAt(i)) % PROJECT_COLORS.length;
  return PROJECT_COLORS[hash];
}

const STATUS_CYCLE   = ['not_started', 'in_progress', 'blocked', 'paused', 'pending_feedback', 'done'];
const PRIORITY_CYCLE = [null, 'high', 'medium', 'low'];

function _statusLabel(s)   { return t('status_' + (s || 'not_started')); }
function _priorityLabel(p) { return p ? t('priority_' + p) : t('priority_none'); }
function _statusCls(s)     { return s || 'not_started'; }
function _priorityCls(p)   { return p || 'none_p'; }

async function loadTaskBoard() {
  const body = document.getElementById('task-board-body');
  if (!body) return;
  body.innerHTML = `<div class="loading">${t('loading_actions')}</div>`;
  _taskData = await pywebview.api.get_tasks();
  renderTaskBoard();
}

function renderTaskBoard() {
  const body = document.getElementById('task-board-body');
  if (!body) return;
  const { projects, tasks } = _taskData;

  const byProject = {};
  tasks.forEach(task => {
    const pid = task.project_id || 'none';
    if (!byProject[pid]) byProject[pid] = [];
    byProject[pid].push(task);
  });

  // La sección "Sin proyecto" se muestra siempre (aunque esté vacía) y va primero,
  // para poder añadir/ver tareas no asociadas a ningún proyecto.
  const sections = [{ id: 'none', name: t('task_no_project') }, ...projects];

  body.innerHTML = sections.map(p => _renderProjectSection(p, byProject[p.id] || [])).join('');
  _bindTaskBoardEvents();
}

function _renderProjectSection(project, projectTasks) {
  const topLevel = projectTasks.filter(t => !t.parent_id);
  const subMap = {};
  projectTasks.forEach(t => {
    if (t.parent_id) { if (!subMap[t.parent_id]) subMap[t.parent_id] = []; subMap[t.parent_id].push(t); }
  });
  const done = topLevel.filter(t => t.status === 'done').length;
  const color = _projectColor(project);

  return `
  <div class="task-project-section" data-project-id="${project.id}">
    <div class="task-project-header" style="border-left-color:${color}" onclick="toggleProjectSection('${project.id}')">
      <span class="task-project-chevron open" style="color:${color}">▶</span>
      <span class="task-project-name" style="color:${color}">${escHtml(project.name)}</span>
      <span class="task-project-count" style="color:${color};background:${color}1a">${done}/${topLevel.length}</span>
    </div>
    <div class="task-project-body" id="proj-body-${project.id}">
      <div class="task-col-headers">
        <span class="task-col-hdr">${t('task_col_name')}</span>
        <span class="task-col-hdr">${t('task_col_status')}</span>
        <span class="task-col-hdr">${t('task_col_assignee')}</span>
        <span class="task-col-hdr">${t('task_col_deadline')}</span>
        <span class="task-col-hdr">${t('task_col_priority')}</span>
        <span></span>
      </div>
      ${topLevel.map(task => _renderTaskRow(task, subMap[task.id] || [], false)).join('')}
      <div class="task-add-row" data-add-project="${project.id}" data-add-parent="">
        <button class="task-add-btn">${t('task_add_task')}</button>
      </div>
    </div>
  </div>`;
}

function _renderTaskRow(task, subitems, isSubitem) {
  const isParent = !isSubitem && subitems.length > 0;
  const cls = [
    'task-row',
    isSubitem ? 'subitem' : '',
    isParent ? 'parent-task' : '',
  ].filter(Boolean).join(' ');
  const doneCls = task.status === 'done' ? ' done' : '';
  const expandBtn = subitems.length
    ? `<button class="task-expand-btn open" data-expand="${task.id}">▶</button>`
    : `<button class="task-expand-btn placeholder" disabled>▶</button>`;
  const srcTag = task.source === 'meeting' && task.meeting_path
    ? `<button class="task-source-btn" data-goto-meeting="${escHtml(task.id)}">↗ ${t('task_from_meeting')}</button>` : '';
  const claudeBadge = task.claude_executable
    ? `<span class="task-claude-badge">✦ Claude</span>` : '';
  const subRows = subitems.map(s => _renderTaskRow(s, [], true)).join('');
  const subAdd = !isSubitem ? `
    <div class="task-add-row subitem-add" data-add-project="${task.project_id}" data-add-parent="${task.id}">
      <button class="task-add-btn">${t('task_add_subitem')}</button>
    </div>` : '';

  return `
  <div class="task-row-wrap" id="taskwrap-${task.id}">
    <div class="${cls}" data-task-id="${task.id}">
      <div class="task-name-cell">
        ${expandBtn}
        <input class="task-title-input${doneCls}" type="text" value="${escHtml(task.title)}"
               title="${escHtml(task.title)}"
               data-task-field="${task.id}:title" placeholder="${t('task_new_ph')}">
        ${claudeBadge}${srcTag}
        <button class="task-row-detail" data-detail-task="${task.id}">···</button>
      </div>
      <div><select class="task-status-select ${_statusCls(task.status)}" data-status-task="${task.id}">
           ${STATUS_CYCLE.map(s => `<option value="${s}" ${task.status === s ? 'selected' : ''}>${_statusLabel(s)}</option>`).join('')}
      </select></div>
      <div><input class="task-cell-input" type="text" value="${escHtml(task.assignee || '')}"
           placeholder="—" data-task-field="${task.id}:assignee"></div>
      <div><input class="task-cell-input" type="text" value="${escHtml(task.deadline || '')}"
           placeholder="—" data-task-field="${task.id}:deadline"></div>
      <div><button class="task-priority-btn ${_priorityCls(task.priority)}"
           data-priority-task="${task.id}">${_priorityLabel(task.priority)}</button></div>
      <button class="task-row-del" data-del-task="${task.id}" title="Eliminar">×</button>
    </div>
    ${subitems.length || !isSubitem ? `<div class="task-subitems" id="subs-${task.id}">${subRows}${subAdd}</div>` : ''}
  </div>`;
}

function toggleProjectSection(projectId) {
  const body = document.getElementById('proj-body-' + projectId);
  const chevron = document.querySelector(`[data-project-id="${projectId}"] .task-project-chevron`);
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : '';
  chevron?.classList.toggle('open', !open);
}

function _refreshProjectCount(projectId) {
  const section = document.querySelector(`[data-project-id="${projectId}"]`);
  if (!section) return;
  const top  = _taskData.tasks.filter(t => t.project_id === projectId && !t.parent_id);
  const done = top.filter(t => t.status === 'done').length;
  const el = section.querySelector('.task-project-count');
  if (el) el.textContent = `${done}/${top.length}`;
}

function _bindTaskBoardEvents() {
  const body = document.getElementById('task-board-body');
  if (!body) return;

  body.querySelectorAll('[data-status-task]').forEach(sel => {
    sel.addEventListener('change', async () => {
      const id = sel.dataset.statusTask;
      const task = _taskData.tasks.find(t => t.id === id);
      if (!task) return;
      const next = sel.value;
      task.status = next;
      sel.className = 'task-status-select ' + _statusCls(next);
      document.querySelector(`[data-task-field="${id}:title"]`)?.classList.toggle('done', next === 'done');
      await pywebview.api.update_task(id, { status: next });
      _refreshProjectCount(task.project_id);
      refreshPendingBadge();
    });
  });

  body.querySelectorAll('[data-priority-task]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.priorityTask;
      const task = _taskData.tasks.find(t => t.id === id);
      if (!task) return;
      const next = PRIORITY_CYCLE[(PRIORITY_CYCLE.indexOf(task.priority) + 1) % PRIORITY_CYCLE.length];
      task.priority = next;
      btn.textContent = _priorityLabel(next);
      btn.className = 'task-priority-btn ' + _priorityCls(next);
      await pywebview.api.update_task(id, { priority: next });
    });
  });

  body.querySelectorAll('[data-task-field]').forEach(input => {
    input.addEventListener('blur', async () => {
      const [id, field] = input.dataset.taskField.split(':');
      const task = _taskData.tasks.find(t => t.id === id);
      if (!task || task[field] === input.value) return;
      task[field] = input.value;
      await pywebview.api.update_task(id, { [field]: input.value });
    });
    input.addEventListener('keydown', e => { if (e.key === 'Enter') input.blur(); });
  });

  body.querySelectorAll('[data-expand]').forEach(btn => {
    btn.addEventListener('click', () => {
      const subsEl = document.getElementById('subs-' + btn.dataset.expand);
      if (!subsEl) return;
      const open = btn.classList.contains('open');
      btn.classList.toggle('open', !open);
      subsEl.style.display = open ? 'none' : '';
    });
  });

  body.querySelectorAll('[data-del-task]').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.dataset.delTask;
      const task = _taskData.tasks.find(t => t.id === id);
      await pywebview.api.delete_task(id);
      _taskData.tasks = _taskData.tasks.filter(t => t.id !== id && t.parent_id !== id);
      document.getElementById('taskwrap-' + id)?.remove();
      if (task?.project_id) _refreshProjectCount(task.project_id);
      refreshPendingBadge();
      // Refrescar acciones de la reunión abierta para que el botón vuelva de
      // "In panel" a "Move to panel". Usamos currentPath (no task.meeting_path)
      // porque el meeting puede haber sido renombrado y el path del task puede
      // estar desactualizado.
      if (task?.meeting_path && currentPath) {
        refreshMeetingActions(currentPath);
      }
    });
  });

  body.querySelectorAll('[data-add-project]').forEach(row => {
    row.addEventListener('click', () => _startAddTask(row));
  });

  body.querySelectorAll('[data-goto-meeting]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const task = _taskData.tasks.find(tk => tk.id === btn.dataset.gotoMeeting);
      if (task?.meeting_path) { showView('meetings'); openMeeting(task.meeting_path); }
    });
  });

  body.querySelectorAll('[data-detail-task]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      openTaskDetail(btn.dataset.detailTask);
    });
  });
}

function _startAddTask(addRow) {
  if (addRow.classList.contains('editing')) return;
  const projectId = addRow.dataset.addProject;
  const parentId  = addRow.dataset.addParent || '';
  addRow.classList.add('editing');
  addRow.innerHTML = `<input class="task-new-input" type="text" placeholder="${t('task_new_ph')}" autofocus>`;
  const input = addRow.querySelector('.task-new-input');
  input.focus();
  let committed = false;
  const commit = async () => {
    if (committed) return; committed = true;
    const title = input.value.trim();
    if (!title) { renderTaskBoard(); return; }
    const task = await pywebview.api.create_task(projectId, title, parentId);
    _taskData.tasks.push(task);
    renderTaskBoard();
    refreshPendingBadge();
  };
  input.addEventListener('blur', commit);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter')  { e.preventDefault(); commit(); }
    if (e.key === 'Escape') { input.value = ''; commit(); }
  });
}

// ── Task detail drawer ────────────────────────────────────────────────────────

let _drawerTaskId = null;

async function openTaskDetail(taskId) {
  const task = _taskData.tasks.find(tk => tk.id === taskId);
  if (!task) return;
  _drawerTaskId = taskId;

  const drawer = document.getElementById('task-detail-drawer');
  const backdrop = document.getElementById('task-drawer-backdrop');
  const body = document.getElementById('task-detail-body');

  body.innerHTML = `<div class="loading">${t('loading')}</div>`;
  drawer.classList.add('open');
  backdrop.classList.add('open');

  // Fetch action data if it comes from a meeting
  let action = null;
  if (task.meeting_path && task.meeting_action_index != null) {
    try { action = await pywebview.api.get_action(task.meeting_path, task.meeting_action_index); } catch (_) {}
  }

  const isClaudeExec = action?.claude_executable;
  const prompt = action?.prompt_enriched || action?.prompt_original || '';
  const statusOpts = STATUS_CYCLE.map(s =>
    `<option value="${s}" ${task.status === s ? 'selected' : ''}>${_statusLabel(s)}</option>`).join('');
  const priorityOpts = PRIORITY_CYCLE.map(p =>
    `<option value="${p ?? ''}" ${(task.priority ?? '') === (p ?? '') ? 'selected' : ''}>${_priorityLabel(p)}</option>`).join('');
  const meetingMeta = task.meeting_path ? _meetingMetaFromPath(task.meeting_path) : null;

  body.innerHTML = `
    <div class="drawer-field">
      <div class="drawer-field-label">${t('task_col_name')}</div>
      <input class="drawer-title-input" id="drawer-title" type="text" value="${escHtml(task.title)}">
    </div>
    <div class="drawer-fields-row">
      <div class="drawer-field">
        <div class="drawer-field-label">${t('task_col_status')}</div>
        <select class="drawer-cell-input" id="drawer-status">${statusOpts}</select>
      </div>
      <div class="drawer-field">
        <div class="drawer-field-label">${t('task_col_priority')}</div>
        <select class="drawer-cell-input" id="drawer-priority">${priorityOpts}</select>
      </div>
    </div>
    <div class="drawer-fields-row">
      <div class="drawer-field">
        <div class="drawer-field-label">${t('task_col_assignee')}</div>
        <input class="drawer-cell-input" id="drawer-assignee" type="text" value="${escHtml(task.assignee || '')}" placeholder="—">
      </div>
      <div class="drawer-field">
        <div class="drawer-field-label">${t('task_col_deadline')}</div>
        <input class="drawer-cell-input" id="drawer-deadline" type="text" value="${escHtml(task.deadline || '')}" placeholder="—">
      </div>
    </div>
    <div class="drawer-field">
      <div class="drawer-field-label">${t('task_col_description')}</div>
      <textarea class="drawer-desc-textarea" id="drawer-description" placeholder="${t('desc_placeholder')}">${escHtml(task.description || '')}</textarea>
    </div>
    ${task.meeting_path ? `
    <div class="drawer-field">
      <div class="drawer-field-label">${t('drawer_meeting_label')}</div>
      <button class="drawer-meeting-card" onclick="_openMeetingFromDrawer()">
        <span class="drawer-meeting-card-icon">📄</span>
        <span class="drawer-meeting-card-info">
          <span class="drawer-meeting-card-title">${escHtml(meetingMeta.title || t('task_from_meeting'))}</span>
          ${meetingMeta.date ? `<span class="drawer-meeting-card-date">${escHtml(meetingMeta.date)}</span>` : ''}
        </span>
        <span class="drawer-meeting-card-arrow">↗</span>
      </button>
    </div>` : ''}
    ${isClaudeExec ? `
    <div class="drawer-field" style="flex:1">
      <div class="drawer-prompt-label">${t('prompt_label')}</div>
      <textarea class="drawer-prompt-textarea" id="drawer-prompt">${escHtml(prompt)}</textarea>
    </div>
    <div class="drawer-btn-row">
      <button class="btn btn-primary btn-sm" id="drawer-launch-btn" onclick="_launchFromDrawer()">${t('btn_launch')}</button>
      <button class="btn btn-ghost btn-sm" onclick="closeTaskDetail()">${t('regen_cancel')}</button>
    </div>` : ''}`;

  // Auto-save fields on change
  const saveField = async (field, getValue) => {
    const val = getValue();
    const update = { [field]: val || null };
    await pywebview.api.update_task(taskId, update);
    const tk = _taskData.tasks.find(t => t.id === taskId);
    if (tk) tk[field] = val || null;
    _refreshProjectCount(tk?.project_id);
    // Sync back to table row
    const titleInput = document.querySelector(`[data-task-field="${taskId}:title"]`);
    if (field === 'title' && titleInput) { titleInput.value = val; titleInput.title = val; }
    if (field === 'status') {
      const statusSel = document.querySelector(`[data-status-task="${taskId}"]`);
      if (statusSel) { statusSel.value = val; statusSel.className = 'task-status-select ' + _statusCls(val); }
      refreshPendingBadge();
    }
  };

  document.getElementById('drawer-title')?.addEventListener('blur', () =>
    saveField('title', () => document.getElementById('drawer-title').value.trim()));
  document.getElementById('drawer-status')?.addEventListener('change', () =>
    saveField('status', () => document.getElementById('drawer-status').value));
  document.getElementById('drawer-priority')?.addEventListener('change', () =>
    saveField('priority', () => document.getElementById('drawer-priority').value || null));
  document.getElementById('drawer-assignee')?.addEventListener('blur', () =>
    saveField('assignee', () => document.getElementById('drawer-assignee').value.trim()));
  document.getElementById('drawer-deadline')?.addEventListener('blur', () =>
    saveField('deadline', () => document.getElementById('drawer-deadline').value.trim()));
  document.getElementById('drawer-description')?.addEventListener('blur', () =>
    saveField('description', () => document.getElementById('drawer-description').value.trim()));

  // Save prompt to meeting JSON on blur
  if (isClaudeExec && task.meeting_path) {
    document.getElementById('drawer-prompt')?.addEventListener('blur', () => {
      const val = document.getElementById('drawer-prompt')?.value || '';
      savePrompt(task.meeting_path, task.meeting_action_index, val);
    });
  }
}

async function _launchFromDrawer() {
  const task = _taskData.tasks.find(tk => tk.id === _drawerTaskId);
  if (!task?.meeting_path) return;
  const prompt = document.getElementById('drawer-prompt')?.value || '';
  await savePrompt(task.meeting_path, task.meeting_action_index, prompt);
  const workingDir = await pywebview.api.get_action_working_dir(task.meeting_path, task.meeting_action_index);
  closeTaskDetail();
  openRunsPanel();
  await globalLaunchRun(task.meeting_path, task.meeting_action_index, workingDir, prompt);
}

function closeTaskDetail() {
  document.getElementById('task-detail-drawer')?.classList.remove('open');
  document.getElementById('task-drawer-backdrop')?.classList.remove('open');
  _drawerTaskId = null;
}

// Devuelve {title, date} de la reunión asociada a partir de su ruta .md
function _meetingMetaFromPath(path) {
  const m = (allMeetings || []).find(mm => mm.path === path);
  if (m) return { title: m.title, date: m.date };
  const base = String(path).split(/[\\/]/).pop().replace(/\.md$/i, '');
  const mm = base.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})_(.*)$/);
  if (mm) return { title: mm[6].replace(/_/g, ' '), date: `${mm[1]}-${mm[2]}-${mm[3]}` };
  return { title: base, date: '' };
}

// Abre la reunión asociada a la tarea del drawer (sin inyectar la ruta en el HTML)
function _openMeetingFromDrawer() {
  const task = _taskData.tasks.find(tk => tk.id === _drawerTaskId);
  if (!task?.meeting_path) return;
  closeTaskDetail();
  showView('meetings');
  openMeeting(task.meeting_path);
}

// ── Recording settings ────────────────────────────────────────────────────────

function renderWhisperOptions(selectedModel) {
  const sel = document.getElementById('whisper-model-select');
  if (!sel) return;
  const models = [
    { value: 'tiny',     key: 'whisper_tiny' },
    { value: 'base',     key: 'whisper_base' },
    { value: 'small',    key: 'whisper_small' },
    { value: 'medium',   key: 'whisper_medium' },
    { value: 'large-v3', key: 'whisper_large' },
  ];
  const cur = selectedModel || sel.value || 'medium';
  sel.innerHTML = models.map(m =>
    `<option value="${m.value}"${cur === m.value ? ' selected' : ''}>${t(m.key)}</option>`
  ).join('');
}

async function loadRecordingSettings() {
  try {
    const s = await pywebview.api.get_settings();
    renderWhisperOptions(s.whisper_model || 'medium');
  } catch (e) {
    renderWhisperOptions('medium');
  }
}

async function saveWhisperModel(model) {
  await pywebview.api.save_settings({ whisper_model: model });
  showToast(t('toast_model_saved'));
}

// ── Per-project field save ────────────────────────────────────────────────────

const _projectSaveTimers = {};

function scheduleProjectSave(pid) {
  clearTimeout(_projectSaveTimers[pid]);
  _projectSaveTimers[pid] = setTimeout(() => saveProjectFields(pid), 800);
}

async function saveProjectFields(pid) {
  const card = document.querySelector(`.project-settings-item[data-proj-id="${pid}"]`);
  if (!card) return;
  const projects = await pywebview.api.get_projects();
  const proj = projects.find(p => p.id === pid);
  if (!proj) return;
  card.querySelectorAll('[data-proj-field]').forEach(input => {
    const field = input.dataset.projField;
    if (field === 'stakeholders') {
      proj.stakeholders = input.value.split(',').map(s => s.trim()).filter(Boolean);
    } else {
      proj[field] = input.value.trim();
    }
  });
  await pywebview.api.save_project(proj);
}

async function openProjectDir(dir) {
  if (!dir || !dir.trim()) return;
  await pywebview.api.open_project_dir(dir.trim());
}

// ── Project settings management ───────────────────────────────────────────────

let _newProjectFolder = '';
let _newProjectColor  = PROJECT_COLORS[0];
let _editingProjectId = null;         // proyecto actualmente en modo edición (o null)

function _renderNewProjectColors() {
  const wrap = document.getElementById('add-proj-color-picker');
  if (!wrap) return;
  wrap.innerHTML = PROJECT_COLORS.map(c =>
    `<button type="button" class="proj-color-swatch${c === _newProjectColor ? ' selected' : ''}" data-color="${c}" style="background:${c}" onclick="selectNewProjectColor(this)" title="${c}"></button>`
  ).join('');
}

function selectNewProjectColor(swatch) {
  _newProjectColor = swatch.dataset.color;
  const wrap = document.getElementById('add-proj-color-picker');
  if (wrap) wrap.querySelectorAll('.proj-color-swatch').forEach(s => s.classList.toggle('selected', s === swatch));
}
const _expandedProjects = new Set();  // ids de proyectos con el detalle desplegado

// ── Carpetas de contexto del proyecto ────────────────────────────────────────
function _contextDirRowHtml(dir) {
  return `<div class="context-dir-row" data-dir="${escHtml(dir)}">
    <svg class="context-dir-ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"><path d="M4 7a2 2 0 0 1 2-2h3.5l2 2H18a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7z"/></svg>
    <span class="context-dir-path">${escHtml(dir)}</span>
    <button class="context-dir-x" title="${t('remove') || 'Quitar'}" onclick="this.closest('.context-dir-row').remove()">✕</button>
  </div>`;
}

async function addEditContextDir(pid) {
  const dir = await pywebview.api.pick_folder();
  if (!dir) return;
  const list = document.getElementById('edit-ctx-list-' + pid);
  if (!list) return;
  if ([...list.querySelectorAll('.context-dir-row')].some(r => r.dataset.dir === dir)) return;
  list.insertAdjacentHTML('beforeend', _contextDirRowHtml(dir));
}

async function addNewContextDir() {
  const dir = await pywebview.api.pick_folder();
  if (!dir) return;
  const list = document.getElementById('add-proj-context-list');
  if (!list) return;
  if ([...list.querySelectorAll('.context-dir-row')].some(r => r.dataset.dir === dir)) return;
  list.insertAdjacentHTML('beforeend', _contextDirRowHtml(dir));
}

function _readContextDirs(listEl) {
  if (!listEl) return [];
  return [...listEl.querySelectorAll('.context-dir-row')].map(r => r.dataset.dir).filter(Boolean);
}

// Guarda las carpetas y extrae sus documentos a la memoria del proyecto,
// en segundo plano, con progreso y opción de cancelar.
async function syncProjectMemory(pid) {
  const btn = document.getElementById('mem-sync-' + pid);
  const status = document.getElementById('mem-status-' + pid);
  // Persistir las carpetas actuales antes de sincronizar
  try {
    const projects = await pywebview.api.get_projects();
    const proj = projects.find(p => p.id === pid);
    if (proj) {
      const card = document.querySelector(`.project-settings-item[data-proj-id="${pid}"]`);
      const ctxList = card ? card.querySelector('.context-dirs-list') : null;
      if (ctxList) { proj.context_dirs = _readContextDirs(ctxList); await pywebview.api.save_project(proj); }
    }
  } catch (_) {}

  try { await pywebview.api.start_project_sync(pid); } catch (_) { showToast(t('mem_failed')); return; }
  if (btn) btn.disabled = true;

  clearInterval(_memPollTimers[pid]);
  _memPollTimers[pid] = setInterval(async () => {
    let s;
    try { s = await pywebview.api.get_project_sync_status(pid); } catch (_) { return; }
    if (!s) return;
    if (!s.done) {
      if (status) status.innerHTML =
        `<span class="mem-status-txt">${t('mem_updating')} ${s.current || 0}/${s.total || '…'}</span>
         <button class="btn btn-ghost btn-sm" onclick="cancelProjectSync('${pid}')">${t('cancel_btn')}</button>`;
    } else {
      clearInterval(_memPollTimers[pid]);
      if (btn) btn.disabled = false;
      if (status) {
        status.textContent = s.cancelled ? t('mem_cancelled')
          : s.error ? t('mem_failed')
          : `${t('mem_updated')}${s.count ? ' (' + s.count + ')' : ''}`;
        setTimeout(() => { if (status && status.dataset.pid === pid) status.textContent = ''; }, 5000);
      }
    }
  }, 800);
}
const _memPollTimers = {};

async function cancelProjectSync(pid) {
  try { await pywebview.api.cancel_project_sync(pid); } catch (_) {}
}

function toggleColorPicker(pid) {
  const picker = document.getElementById(`color-picker-${pid}`);
  if (!picker) return;
  picker.style.display = picker.style.display === 'none' ? 'flex' : 'none';
}

function selectProjectColor(swatch, pid) {
  const picker = document.getElementById(`color-picker-${pid}`);
  if (picker) {
    picker.querySelectorAll('.proj-color-swatch').forEach(s => s.classList.remove('selected'));
    swatch.classList.add('selected');
    picker.style.display = 'none';
  }
  const trigger = document.querySelector(`[data-color-trigger="${pid}"]`);
  if (trigger) { trigger.style.background = swatch.dataset.color; trigger.dataset.color = swatch.dataset.color; }
}

function toggleProjectDetail(pid) {
  const card = document.querySelector(`.project-settings-item[data-proj-id="${pid}"]`);
  if (!card) return;
  const detail = card.querySelector('.project-settings-detail');
  const chev = card.querySelector('.project-chevron');
  const willExpand = !_expandedProjects.has(pid);
  if (willExpand) _expandedProjects.add(pid); else _expandedProjects.delete(pid);
  if (detail) detail.style.display = willExpand ? '' : 'none';
  if (chev) chev.textContent = willExpand ? '▾' : '▸';
  card.classList.toggle('expanded', willExpand);
}

async function loadProjectsSettings(editingId = null) {
  _editingProjectId = editingId;
  const projects = await pywebview.api.get_projects();
  const list = document.getElementById('projects-list-settings');
  if (!list) return;
  if (!projects.length) {
    list.innerHTML = `<div style="font-size:12px;color:var(--muted);padding:4px 0">${t('no_projects')}</div>`;
    return;
  }
  list.innerHTML = projects.map(p => {
    const pid = escHtml(p.id);
    const hasFolder = !!(p.output_dir && p.output_dir.trim());
    const isEditing = editingId === pid;
    if (isEditing) _expandedProjects.add(p.id);  // mantener abierto al editar
    const isExpanded = isEditing || _expandedProjects.has(p.id);

    const color = _projectColor(p);
    const colorSwatches = PROJECT_COLORS.map(c =>
      `<button class="proj-color-swatch${c === color ? ' selected' : ''}" data-color="${c}" style="background:${c}" onclick="selectProjectColor(this,'${pid}')" title="${c}"></button>`
    ).join('');

    const headerRow = isEditing ? `
      <div style="display:flex;flex-direction:column;gap:6px">
        <input class="settings-text-input" id="edit-proj-name-${pid}" value="${escHtml(p.name)}" style="font-size:13px;font-weight:600">
        <input class="settings-text-input" id="edit-proj-desc-${pid}" value="${escHtml(p.description || '')}" placeholder="${t('proj_desc_ph')}" style="font-size:12px">
      </div>
    ` : `
      <div class="project-settings-row" onclick="toggleProjectDetail('${pid}')">
        <div style="min-width:0;flex:1">
          <div class="project-settings-name">${escHtml(p.name)}</div>
          ${p.description ? `<div class="project-settings-desc">${escHtml(p.description)}</div>` : ''}
        </div>
        <span class="project-chevron">${isExpanded ? '▾' : '▸'}</span>
      </div>
    `;

    const detailActions = isEditing ? `
      <div style="display:flex;gap:4px;justify-content:flex-end;margin-bottom:8px">
        <button class="btn btn-primary btn-sm" onclick="saveEditProject('${pid}')">${t('save_btn')}</button>
        <button class="btn btn-ghost btn-sm" onclick="loadProjectsSettings()">${t('cancel_btn')}</button>
      </div>
    ` : `
      <div style="display:flex;gap:4px;justify-content:flex-end;margin-bottom:4px">
        <button class="btn btn-ghost btn-sm" onclick="loadProjectsSettings('${pid}')">${t('edit_btn')}</button>
        <button class="btn btn-delete btn-sm" onclick="deleteProject('${pid}')">✕</button>
      </div>`;

    const fieldsDisabled = isEditing ? '' : 'disabled';
    const canEditExport = isEditing && hasFolder;
    const boxChecked = f => (hasFolder && p['export_save_' + f] !== false) ? 'checked' : '';

    return `
    <div class="project-settings-item${isExpanded ? ' expanded' : ''}" data-proj-id="${pid}" style="border-left-color:${color}">
      ${headerRow}
      <div class="project-settings-detail"${isExpanded ? '' : ' style="display:none"'}>
        ${detailActions}
        ${isEditing ? `
        <div style="margin-top:4px;margin-bottom:4px">
          <div class="proj-field-label" style="margin-bottom:6px">${t('proj_color_label')}</div>
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <button class="proj-color-swatch" data-color-trigger="${pid}" data-color="${color}" style="background:${color}" onclick="toggleColorPicker('${pid}')" title="${t('proj_color_label')}"></button>
            <div class="proj-color-picker" id="color-picker-${pid}" style="display:none">${colorSwatches}</div>
          </div>
        </div>` : ''}
        <div style="margin-top:8px">
          <div class="proj-field-label">${t('proj_stake_label')}</div>
          <div class="settings-card-desc" style="margin:3px 0 5px">${t('proj_stake_desc')}</div>
          <input class="settings-text-input" value="${escHtml((p.stakeholders||[]).join(', '))}"
            data-proj-field="stakeholders" ${fieldsDisabled}>
        </div>
        <div style="margin-top:12px">
          <div class="proj-field-label">${t('proj_dir_label')}</div>
          <div class="settings-card-desc" style="margin:3px 0 5px">${t('proj_dir_desc')}</div>
          <div class="proj-folder-row">
            <span class="proj-folder-path ${hasFolder ? '' : 'empty'}" id="proj-folder-display-${pid}">${hasFolder ? escHtml(p.output_dir) : t('proj_folder_default')}</span>
            ${isEditing ? `<button class="btn btn-ghost btn-sm" onclick="browseProjectFolder('${pid}')">${t('proj_folder_browse')}</button>` : ''}
            ${isEditing && hasFolder ? `<button class="btn btn-ghost btn-sm" onclick="clearProjectFolder('${pid}')" title="${t('proj_folder_clear')}">✕</button>` : ''}
          </div>
        </div>
        <div style="margin-top:12px">
          <div class="proj-field-label">${t('proj_context_label')}</div>
          <div class="settings-card-desc" style="margin:3px 0 6px">${t('proj_context_desc')}</div>
          <div id="edit-ctx-list-${pid}" class="context-dirs-list">
            ${(p.context_dirs || []).map(d => _contextDirRowHtml(d)).join('')}
          </div>
          ${isEditing ? `<div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap">
            <button class="btn btn-ghost btn-sm" onclick="addEditContextDir('${pid}')">+ ${t('proj_context_add')}</button>
            <button class="btn btn-primary btn-sm" id="mem-sync-${pid}" onclick="syncProjectMemory('${pid}')">${t('mem_update')}</button>
          </div>
          <div class="mem-status" id="mem-status-${pid}" data-pid="${pid}"></div>` : ''}
        </div>
        <div style="margin-top:12px">
          <div class="proj-field-label">${t('export_settings_title')}</div>
          <div class="settings-card-desc" style="margin:3px 0 8px">${t('export_settings_desc_project')}</div>
          <div style="display:flex;flex-direction:column;gap:8px">
            <label class="proj-export-check${canEditExport ? '' : ' disabled'}">
              <input type="checkbox" data-export-field="html" ${boxChecked('html')} ${canEditExport ? '' : 'disabled'}>
              <span data-i18n="export_html">${t('export_html')}</span>
            </label>
            <label class="proj-export-check${canEditExport ? '' : ' disabled'}">
              <input type="checkbox" data-export-field="email" ${boxChecked('email')} ${canEditExport ? '' : 'disabled'}>
              <span data-i18n="export_email">${t('export_email')}</span>
            </label>
            <label class="proj-export-check${canEditExport ? '' : ' disabled'}">
              <input type="checkbox" data-export-field="transcript" ${boxChecked('transcript')} ${canEditExport ? '' : 'disabled'}>
              <span data-i18n="export_transcript">${t('export_transcript')}</span>
            </label>
          </div>
          ${!hasFolder ? `<div class="settings-card-desc" style="margin-top:6px;color:var(--muted)">${t('export_needs_folder')}</div>` : ''}
        </div>
      </div>
    </div>`;
  }).join('');
}

async function saveEditProject(pid) {
  const nameInput = document.getElementById(`edit-proj-name-${pid}`);
  const descInput = document.getElementById(`edit-proj-desc-${pid}`);
  if (!nameInput) return;
  const name = nameInput.value.trim();
  if (!name) return;
  const projects = await pywebview.api.get_projects();
  const proj = projects.find(p => p.id === pid);
  if (!proj) return;
  proj.name = name;
  proj.description = descInput ? descInput.value.trim() : '';

  const card = document.querySelector(`.project-settings-item[data-proj-id="${pid}"]`);
  if (card) {
    // Color
    const trigger = card.querySelector('[data-color-trigger]');
    if (trigger) proj.color = trigger.dataset.color;
    // Stakeholders
    const stakeInput = card.querySelector('[data-proj-field="stakeholders"]');
    if (stakeInput) {
      proj.stakeholders = stakeInput.value.split(',').map(s => s.trim()).filter(Boolean);
    }
    // Carpetas de contexto (memoria del proyecto)
    const ctxList = card.querySelector('.context-dirs-list');
    if (ctxList) proj.context_dirs = _readContextDirs(ctxList);
    // Export flags: solo si hay carpeta configurada (si no, se preservan)
    const hasFolder = !!(proj.output_dir && proj.output_dir.trim());
    if (hasFolder) {
      const get = f => card.querySelector(`[data-export-field="${f}"]`);
      if (get('html'))       proj.export_save_html       = get('html').checked;
      if (get('email'))      proj.export_save_email      = get('email').checked;
      if (get('transcript')) proj.export_save_transcript = get('transcript').checked;
    }
  }

  await pywebview.api.save_project(proj);
  await loadProjectsSettings();
  await _refreshProjectsCache();
}

// Recarga la caché global de proyectos y repinta la barra lateral (para que el
// color/nombre nuevo se refleje al instante en Notas → Proyectos y en el board).
async function _refreshProjectsCache() {
  allProjects = await pywebview.api.get_projects();
  if (typeof allMeetings !== 'undefined' && allMeetings) renderSidebar(allMeetings);
}

function showAddProjectForm() {
  document.getElementById('add-project-form').style.display = 'block';
  _newProjectColor = PROJECT_COLORS[0];
  _renderNewProjectColors();
  document.getElementById('proj-name').focus();
}

function hideAddProjectForm() {
  document.getElementById('add-project-form').style.display = 'none';
  document.getElementById('proj-name').value = '';
  document.getElementById('proj-desc').value = '';
  document.getElementById('proj-stakeholders').value = '';
  _newProjectFolder = '';
  _newProjectColor = PROJECT_COLORS[0];
  const ctxList = document.getElementById('add-proj-context-list');
  if (ctxList) ctxList.innerHTML = '';
  const display = document.getElementById('add-proj-folder-display');
  if (display) { display.textContent = t('proj_folder_default'); display.classList.add('empty'); }
}

async function saveNewProject() {
  const name = document.getElementById('proj-name').value.trim();
  if (!name) return;
  const description = document.getElementById('proj-desc').value.trim();
  const stakeholders = document.getElementById('proj-stakeholders').value
    .split(',').map(s => s.trim()).filter(Boolean);
  const context_dirs = _readContextDirs(document.getElementById('add-proj-context-list'));
  await pywebview.api.save_project({ name, description, stakeholders, output_dir: _newProjectFolder, color: _newProjectColor, context_dirs });
  hideAddProjectForm();
  await loadProjectsSettings();
  await _refreshProjectsCache();
}

// ── Modal de confirmación genérico ────────────────────────────────────────────

let _confirmCallback = null;

function openConfirmModal(message, onConfirm, { title = '', okLabel = '' } = {}) {
  _confirmCallback = onConfirm;
  const msgEl = document.getElementById('confirm-modal-msg');
  if (msgEl) msgEl.textContent = message;
  const titleEl = document.getElementById('confirm-modal-title');
  if (titleEl) titleEl.textContent = title || t('confirm_delete_title');
  const okBtn = document.getElementById('confirm-modal-ok');
  if (okBtn) {
    okBtn.textContent = okLabel || t('btn_delete');
    okBtn.onclick = () => {
      const cb = _confirmCallback;
      closeConfirmModal();
      if (cb) cb();
    };
  }
  document.getElementById('confirm-modal').classList.remove('hidden');
}

function closeConfirmModal() {
  _confirmCallback = null;
  document.getElementById('confirm-modal').classList.add('hidden');
}

async function deleteProject(id) {
  let name = '';
  try {
    const projects = await pywebview.api.get_projects();
    const proj = projects.find(p => p.id === id);
    if (proj) name = proj.name;
  } catch (_) {}
  openConfirmModal(
    t('confirm_delete_project', name),
    async () => {
      await pywebview.api.delete_project(id);
      allProjects = await pywebview.api.get_projects();
      await loadProjectsSettings();
    },
    { title: t('confirm_delete_title') },
  );
}

async function browseProjectFolder(pid) {
  const path = await pywebview.api.browse_project_folder();
  if (!path) return;
  const projects = await pywebview.api.get_projects();
  const proj = projects.find(p => p.id === pid);
  if (!proj) return;
  proj.output_dir = path;
  await pywebview.api.save_project(proj);
  await loadProjectsSettings(_editingProjectId);  // mantener el modo edición si estaba activo
}

async function clearProjectFolder(pid) {
  const projects = await pywebview.api.get_projects();
  const proj = projects.find(p => p.id === pid);
  if (!proj) return;
  proj.output_dir = '';
  await pywebview.api.save_project(proj);
  await loadProjectsSettings(_editingProjectId);  // mantener el modo edición si estaba activo
}

async function browseNewProjectFolder() {
  const path = await pywebview.api.browse_project_folder();
  if (!path) return;
  _newProjectFolder = path;
  const display = document.getElementById('add-proj-folder-display');
  if (display) { display.textContent = path; display.classList.remove('empty'); }
}

// ── Parseo de fechas de deadline ──────────────────────────────────────────────

const _MONTHS = {
  jan:1, january:1, ene:1, enero:1,
  feb:2, february:2, febrero:2,
  mar:3, march:3, marzo:3,
  apr:4, april:4, abr:4, abril:4,
  may:5, mayo:5,
  jun:6, june:6, junio:6,
  jul:7, july:7, julio:7,
  aug:8, august:8, ago:8, agosto:8,
  sep:9, sept:9, september:9, septiembre:9,
  oct:10, october:10, octubre:10,
  nov:11, november:11, noviembre:11,
  dec:12, december:12, dic:12, diciembre:12,
};

// ── Grupos de deadline ────────────────────────────────────────────────────────
// Grupo 1 → '0000-00-00'  ASAP / inmediato (siempre primero)
// Grupo 2 → 'YYYY-MM-DD'  Fecha real parseada
// Grupo 3 → '8888-88-88'  Relativo sin fecha concreta (esta semana, antes de X…)
// Grupo 4 → '9999-99-99'  Indefinido / sin fecha (TBD, por definir, ongoing…)

const _ASAP_TERMS = [
  'lo antes posible', 'cuanto antes', 'asap', 'as soon as possible',
  'urgente', 'urgent', 'inmediato', 'inmediatamente', 'immediate', 'immediately',
  'same session', 'prioritario', 'priority',
  'hoy', 'today', '~1 day', '1 day',
];

const _RELATIVE_TERMS = [
  'esta semana', 'this week', 'next week', 'la semana que viene',
  'antes de reunión', 'antes de la reunión', 'before the meeting',
  'after meeting', 'after speaking', 'after the call', 'en call', 'en la call',
  'with quick wins', 'proactively', '~3 weeks', '~2 weeks', 'weeks', 'semanas',
];

const _UNDEFINED_TERMS = [
  'tbd', 'por definir', 'en curso', 'ongoing', 'no deadline', 'none',
  'no date', 'sin fecha', 'pendiente', 'internal discussion',
  'structured approval', 'no hard date',
];

function parseDeadlineSortKey(str) {
  if (!str) return '9999-99-99';
  const s = str.toLowerCase().trim();

  // Grupo 1: ASAP
  if (_ASAP_TERMS.some(term => s.includes(term))) return '0000-00-00';

  // ISO directo
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;

  // Grupo 2: intentar extraer fecha real
  const yearM = s.match(/\b(20\d{2})\b/);
  const year  = yearM ? yearM[1] : String(new Date().getFullYear());

  const monthKeys = Object.keys(_MONTHS).sort((a, b) => b.length - a.length);
  let month = null;
  for (const key of monthKeys) {
    if (s.includes(key)) { month = _MONTHS[key]; break; }
  }

  if (month) {
    const sNoYear = s.replace(/\b20\d{2}\b/g, '');
    const dayM    = sNoYear.match(/\b([12]?\d|3[01])\b/);
    let day = dayM ? parseInt(dayM[1]) : 1;
    if (day < 1 || day > 31) day = 1;
    if (/\bend\b/.test(s)) day = 28;
    return `${year}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;
  }

  // Grupo 3: relativo sin fecha
  if (_RELATIVE_TERMS.some(term => s.includes(term))) return '8888-88-88';

  // Grupo 4: indefinido (default)
  return '9999-99-99';
}

// ── Acciones ──────────────────────────────────────────────────────────────────

let _pendingPanelAction = null;

async function moveToPanel(path, index, btn) {
  const data = await pywebview.api.get_tasks();
  const projSelect = document.getElementById('modal-project-select');
  projSelect.innerHTML = (data.projects || []).map(p =>
    `<option value="${escHtml(p.id)}">${escHtml(p.name)}</option>`
  ).join('') + `<option value="none">${t('task_no_project')}</option>`;
  const meeting = allMeetings.find(m => m.path === path);
  if (meeting?.project_id) projSelect.value = meeting.project_id;
  _populateParentSelect(projSelect.value, data.tasks || []);
  projSelect.onchange = () => _populateParentSelect(projSelect.value, data.tasks || []);
  _pendingPanelAction = { path, index, btn };
  document.getElementById('panel-modal').classList.remove('hidden');
}

function _populateParentSelect(projectId, tasks) {
  const sel = document.getElementById('modal-parent-select');
  const top = tasks.filter(tk => tk.project_id === projectId && !tk.parent_id);
  sel.innerHTML = `<option value="">${t('modal_parent_none')}</option>` +
    top.map(tk => `<option value="${escHtml(tk.id)}">${escHtml(tk.title)}</option>`).join('');
}

function closePanelModal() {
  document.getElementById('panel-modal').classList.add('hidden');
  _pendingPanelAction = null;
}

async function confirmMoveToPanel() {
  if (!_pendingPanelAction) return;
  const { path, index, btn } = _pendingPanelAction;
  const projectId = document.getElementById('modal-project-select').value;
  const parentId  = document.getElementById('modal-parent-select').value;
  closePanelModal();
  const taskId = await pywebview.api.move_action_to_panel(path, index, projectId, parentId || null);
  if (taskId) {
    btn.textContent = t('btn_in_panel');
    btn.classList.add('btn-in-panel');
    btn.disabled = true;
    await refreshPendingBadge();
    showToast(t('toast_moved'));
  }
}

async function deleteAction(path, index, btn) {
  await pywebview.api.delete_action(path, index);
  const card = document.getElementById('card-' + index);
  if (card) card.remove();
  showToast(t('toast_deleted'));
}

async function browseRunDir(index) {
  const folder = await pywebview.api.pick_folder();
  if (folder) {
    const el = document.getElementById('dir-' + index);
    if (el) { el.value = folder; _showDirHint(index, folder); }
  }
}

async function browseRunFile(index) {
  const filePath = await pywebview.api.pick_file();
  if (!filePath) return;
  const dirEl = document.getElementById('dir-' + index);
  if (dirEl) dirEl.value = filePath;
  _showDirHint(index, filePath);
  // Inject the concrete file path at the top of the prompt so Claude knows exactly where the file is
  const promptEl = document.getElementById('prompt-' + index);
  if (promptEl && !promptEl.value.includes(filePath)) {
    promptEl.value = `Archivo: ${filePath}\n\n${promptEl.value}`;
    if (currentPath) savePrompt(currentPath, index, promptEl.value);
  }
}

async function launchRun(path, index) {
  const dirInput  = document.getElementById('dir-' + index);
  const promptEl  = document.getElementById('prompt-' + index);
  const workingDir = dirInput  ? dirInput.value.trim()  : '';
  let prompt       = promptEl  ? promptEl.value.trim()  : '';
  // For document_change: if user typed a file path directly (not via browse button which already injects it),
  // prepend the path so Claude knows exactly which file to work on
  if (workingDir && document.querySelector(`[data-browse-file="${index}"]`) && !prompt.includes(workingDir)) {
    prompt = `File: ${workingDir}\n\n${prompt}`;
  }
  const runId = await pywebview.api.execute_action_panel(path, index, workingDir, prompt);
  if (runId) {
    addRunCard(runId);
    openRunsPanel();
    // Close card body
    document.getElementById('body-' + index)?.classList.remove('open');
  } else {
    showToast(t('toast_terminal'));
    await pywebview.api.execute_action(path, index);
  }
}


async function globalLaunchRun(path, index, workingDir, prompt) {
  const runId = await pywebview.api.execute_action_panel(path, index, workingDir, prompt);
  if (runId) {
    addRunCard(runId);
    openRunsPanel();
  } else {
    showToast(t('toast_terminal'));
    await pywebview.api.execute_action(path, index);
  }
}

async function markDone(path, index) {
  await pywebview.api.mark_done(path, index);
  const card = document.getElementById('card-' + index);
  if (card) {
    card.classList.add('done');
    card.querySelector('.action-title')?.classList.add('done-text');
    const execBtn = card.querySelector('[data-exec]');
    if (execBtn) { execBtn.textContent = t('btn_reexecute'); execBtn.className = 'btn btn-ghost btn-sm'; }
    const doneBtn = card.querySelector('[data-done]');
    if (doneBtn) { doneBtn.textContent = t('btn_done_state'); doneBtn.style.opacity = '0.5'; }
  }
  await refreshPendingBadge();
  showToast(t('toast_done'));
}

async function globalMarkDone(path, index, gi) {
  await pywebview.api.mark_done(path, index);

  // Sync in-memory state so filter re-renders (pending↔done) stay consistent
  const action = allPending.find(a => a.minutes_path === path && a.index === index);
  if (action) action.executed = true;

  const item = document.getElementById('gitem-' + gi);
  if (item) {
    item.classList.add('done');
    item.querySelector('.global-action-title')?.classList.add('done-text');
    const btn = item.querySelector('[data-gcheck]');
    if (btn) { btn.textContent = t('btn_done_state'); btn.style.opacity = '0.5'; }
  }
  await refreshPendingBadge();
  showToast(t('toast_done'));
}

async function savePrompt(path, index, value) {
  await pywebview.api.update_prompt(path, index, value);
}

async function reenrichMeeting(path) {
  const btn = document.getElementById('btn-reenrich');
  if (btn) { btn.disabled = true; btn.textContent = '...'; }
  const actionsDiv = document.getElementById('meeting-actions');
  if (actionsDiv) actionsDiv.innerHTML = `<div style="color:var(--muted);font-size:13px">${t('toast_enriching')}</div>`;
  showToast(t('toast_enriching'));
  await pywebview.api.enrich_actions(path);
  // Espera hasta 60s a que Claude termine el análisis
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 2000));
    const actions = await pywebview.api.get_actions(path);
    if (actions && actions.length > 0) {
      const mtg = allMeetings.find(m => m.path === path) || {};
      renderActionCards(actions, path, actionsDiv, mtg.date || '');
      _renderAddActionBtn(path, actionsDiv);
      const count = document.querySelector('.actions-count');
      if (count) count.textContent = t('n_total', actions.length);
      if (btn) { btn.disabled = false; btn.innerHTML = `↺ ${t('btn_reenrich')}`; }
      return;
    }
  }
  await openMeeting(path);
}

async function sendEmail(path) {
  showToast(t('toast_outlook'));
  await pywebview.api.send_email(path);
}

async function onMeetingProjectChange(projectId) {
  if (!currentPath) return;
  await pywebview.api.set_meeting_project(currentPath, projectId);
  const m = allMeetings.find(m => m.path === currentPath);
  if (m) m.project_id = projectId;
  renderSidebar(allMeetings);
  showToast(t('toast_project_set'));

  if (projectId && projectId !== 'none') {
    const result = await pywebview.api.export_to_project(currentPath);
    if (result === '') showToast(t('toast_export_ok'));
    else if (result === 'no_directory') showToast(t('toast_export_no_dir'));
  }
}

async function detectProjectsForAll() {
  showToast(t('toast_detecting'));
  await pywebview.api.detect_projects_for_all();
  // Reload meetings after a short delay to pick up new assignments
  setTimeout(async () => {
    const meetings = await pywebview.api.get_meetings();
    allMeetings = meetings;
    meetings.forEach((m, i) => { meetingPaths[i] = m.path; });
    renderSidebar(meetings);
  }, 3000);
}

async function openHtml(path) {
  await pywebview.api.open_html(path);
}

// ── Badge ─────────────────────────────────────────────────────────────────────

async function refreshPendingBadge() {
  const data  = await pywebview.api.get_tasks();
  const tasks = (data && data.tasks) || [];
  const count = tasks.filter(t => t.status !== 'done').length;
  const badge = document.getElementById('pending-badge');
  if (!badge) return;
  badge.style.display = count > 0 ? 'flex' : 'none';
  badge.textContent   = count > 9 ? '9+' : String(count);
}

// ── Búsqueda ──────────────────────────────────────────────────────────────────

function onSearch(query) {
  clearTimeout(searchTimeout);
  if (!query.trim()) { renderSidebar(allMeetings); return; }
  searchTimeout = setTimeout(async () => {
    const results = await pywebview.api.search(query);
    results.forEach((m, i) => { meetingPaths[i] = m.path; });
    renderSidebar(results);
    _highlightSidebar(query);
  }, 300);
}

// Resalta el término buscado en los títulos de la lista lateral
function _highlightSidebar(query) {
  const q = query.trim();
  if (!q) return;
  const rx = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig');
  document.querySelectorAll('#meetings-list .meeting-title').forEach(el => {
    const text = el.textContent;
    el.innerHTML = text.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]))
                       .replace(rx, '<mark class="search-hit">$1</mark>');
  });
}

// ── Atajos de teclado ────────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
  const mod = e.ctrlKey || e.metaKey;
  // Ctrl/Cmd+F o Ctrl+K → ir a Notas y enfocar la búsqueda
  if (mod && (e.key === 'f' || e.key === 'k')) {
    e.preventDefault();
    showView('meetings');
    const s = document.getElementById('search-input');
    if (s) { s.focus(); s.select(); }
    return;
  }
  // Ctrl+1..6 → cambiar de vista
  if (mod && ['1', '2', '3', '4', '5', '6'].includes(e.key)) {
    e.preventDefault();
    const views = ['meetings', 'actions', 'projects', 'status', 'trash', 'settings'];
    showView(views[+e.key - 1]);
    return;
  }
  // Esc → cerrar menús/modales abiertos
  if (e.key === 'Escape') {
    const ctx = document.getElementById('meeting-ctx-menu');
    if (ctx) ctx.classList.add('hidden');
    document.getElementById('action-menu')?.classList.add('hidden');
    document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => m.classList.add('hidden'));
  }
});

// Cerrar el menú "más acciones" al hacer clic fuera
document.addEventListener('click', (e) => {
  const menu = document.getElementById('action-menu');
  if (!menu || menu.classList.contains('hidden')) return;
  if (e.target.closest('#btn-more') || e.target.closest('#action-menu')) return;
  menu.classList.add('hidden');
});

// ── Utils ─────────────────────────────────────────────────────────────────────

async function openMinutesInClaude(path) {
  // Abre siempre en terminal (sin picker). El transcript va como contexto.
  const noTranscript = currentLang === 'es'
    ? 'No hay transcripción disponible para esta reunión'
    : 'No transcript available for this meeting';
  const ok = await pywebview.api.open_minutes_in_claude(path, currentLang);
  if (!ok) showToast(noTranscript, 'error');
}


function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 2500);
}

// ── Settings ──────────────────────────────────────────────────────────────────

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
}

async function initSettings() {
  let savedLang = 'es';
  let savedTheme = 'light';
  try {
    const s = await pywebview.api.get_settings();
    savedLang  = s.language || localStorage.getItem('lang')  || 'es';
    savedTheme = s.theme    || localStorage.getItem('theme') || 'light';
  } catch (e) {
    savedLang  = localStorage.getItem('lang')  || 'es';
    savedTheme = localStorage.getItem('theme') || 'light';
  }
  localStorage.setItem('lang',  savedLang);
  localStorage.setItem('theme', savedTheme);
  applyTheme(savedTheme);
  applyLang(savedLang);

  document.querySelectorAll('#theme-toggle .toggle-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.themeVal === savedTheme);
  });
  document.querySelectorAll('#lang-toggle .toggle-btn').forEach(b => {
    b.classList.toggle('active', b.dataset.lang === savedLang);
  });

  document.querySelectorAll('#theme-toggle .toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const theme = btn.dataset.themeVal;
      applyTheme(theme);
      localStorage.setItem('theme', theme);
      document.querySelectorAll('#theme-toggle .toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await pywebview.api.save_settings({ theme });
      showToast(t('settings_saved'));
    });
  });

  document.querySelectorAll('#lang-toggle .toggle-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const lang = btn.dataset.lang;
      localStorage.setItem('lang', lang);
      applyLang(lang);
      document.querySelectorAll('#lang-toggle .toggle-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      await pywebview.api.save_settings({ language: lang });
      showToast(t('settings_saved'));
    });
  });

  const nameInput = document.getElementById('user-name-input');
  if (nameInput) {
    pywebview.api.get_settings().then(s => {
      nameInput.value = s.user_name || '';
    });
    const saveNameBtn = document.getElementById('btn-save-name');
    if (saveNameBtn) {
      saveNameBtn.addEventListener('click', async () => {
        await pywebview.api.save_settings({ user_name: nameInput.value.trim() });
        showToast(t('settings_saved'));
      });
    }
    nameInput.addEventListener('keydown', async e => {
      if (e.key === 'Enter') {
        await pywebview.api.save_settings({ user_name: nameInput.value.trim() });
        showToast(t('settings_saved'));
      }
    });
  }
}

// ── Panel de ejecuciones en paralelo ─────────────────────────────────────────

const _runTimers = {};  // runId → setInterval id

function openRunsPanel() {
  if (document.getElementById('view-meetings').classList.contains('hidden')) {
    showView('meetings');
  }
  document.getElementById('runs-panel').classList.add('open');
  document.getElementById('runs-panel-title').textContent = t('runs_panel_title');
  updateRunsFab();
}

function closeRunsPanel() {
  document.getElementById('runs-panel').classList.remove('open');
  updateRunsFab();
}

function updateRunsFab() {
  const fab   = document.getElementById('runs-toggle-fab');
  const dot   = document.getElementById('runs-fab-dot');
  const label = document.getElementById('runs-fab-label');
  if (!fab) return;
  const list    = document.getElementById('runs-list');
  const total   = list?.children.length || 0;
  const running = list ? [...list.children].filter(c => c.querySelector('.run-card-status.running')).length : 0;
  const panelOpen = document.getElementById('runs-panel')?.classList.contains('open');
  if (total === 0 || panelOpen) { fab.style.display = 'none'; return; }
  fab.style.display = 'flex';
  if (dot)   { dot.classList.toggle('active', running > 0); }
  if (label) {
    label.textContent = running > 0
      ? `${running} ${t('runs_fab_running')}`
      : `${total} ${t('runs_fab_done')}`;
  }
}

const _runStartTimes = {};
const _runMeta = {};  // runId → {path, index, proj_path} populated on done

function _needsConversation(output) {
  if (!output || output.length < 10) return false;
  const tail = output.trimEnd().slice(-400).toLowerCase();
  // Ends with a question mark, or contains common clarification phrases
  if (/\?\s*$/.test(tail)) return true;
  return ['could you', 'please provide', 'please clarify', 'i need more info',
          'which would you', 'should i ', 'let me know if', 'do you want',
          'podrías', '¿', 'necesito saber', 'puedes indicar', 'me indicas',
          'qué prefieres', 'cuál prefieres'].some(p => tail.includes(p));
}

async function continueInTerminal(runId) {
  const meta = _runMeta[runId];
  if (!meta) return;
  await pywebview.api.continue_in_terminal(meta.path, meta.index, meta.proj_path, meta.output || '');
}

function addRunCard(runId) {
  _runStartTimes[runId] = Date.now();
  const list = document.getElementById('runs-list');
  const card = document.createElement('div');
  card.className = 'run-card';
  card.id = 'run-card-' + runId;
  card.innerHTML = `
    <div class="run-card-header">
      <span class="run-card-title" id="runtitle-${runId}">...</span>
      <span class="run-card-status running" id="runstatus-${runId}">
        <span class="run-spinner"></span>${t('run_running')} <span id="runtimer-${runId}">0s</span>
      </span>
    </div>
    <div class="run-card-dir" id="rundir-${runId}"></div>
    <div class="run-card-footer" id="runfooter-${runId}">
      <button class="btn btn-ghost btn-sm" onclick="dismissRun('${runId}')">${t('btn_delete')}</button>
    </div>`;
  list.prepend(card);
  _runTimers[runId] = setInterval(() => pollRun(runId), 700);
  updateRunsFab();
}

function _fmtElapsed(runId) {
  const secs = Math.floor((Date.now() - (_runStartTimes[runId] || Date.now())) / 1000);
  if (secs < 60) return secs + 's';
  return Math.floor(secs / 60) + 'm ' + (secs % 60) + 's';
}

async function pollRun(runId) {
  try {
    const s = await pywebview.api.get_action_run_status(runId);
    const titleEl  = document.getElementById('runtitle-'  + runId);
    const statusEl = document.getElementById('runstatus-' + runId);
    const dirEl    = document.getElementById('rundir-'    + runId);
    if (titleEl  && s.title)     titleEl.textContent = s.title;
    if (dirEl    && s.proj_path) dirEl.textContent   = s.proj_path;
    const timerEl = document.getElementById('runtimer-' + runId);
    if (timerEl && !s.done) timerEl.textContent = _fmtElapsed(runId);
    if (s.done) {
      clearInterval(_runTimers[runId]);
      delete _runTimers[runId];
      _runMeta[runId] = {path: s.path || '', index: s.index ?? -1, proj_path: s.proj_path || '', output: s.output || ''};
      const needsChat = !s.error && _needsConversation(s.output);
      if (statusEl) {
        statusEl.innerHTML = s.error
          ? t('run_error') + ': ' + s.error
          : needsChat ? t('run_needs_input') : t('run_done');
        statusEl.className = 'run-card-status ' + (s.error ? 'error' : needsChat ? 'pending' : 'done');
      }
      updateRunsFab();
      const footerEl = document.getElementById('runfooter-' + runId);
      if (footerEl) {
        footerEl.innerHTML = `
          <button class="btn btn-ghost btn-sm" onclick="continueInTerminal('${runId}')">${t('btn_continue_terminal')}</button>
          <button class="btn btn-ghost btn-sm" onclick="dismissRun('${runId}')">${t('btn_delete')}</button>`;
      }
      if (!s.error && s.path && s.path === currentPath) openMeeting(s.path);
    }
  } catch (e) {
    clearInterval(_runTimers[runId]);
    delete _runTimers[runId];
  }
}

function dismissRun(runId) {
  if (_runTimers[runId]) { clearInterval(_runTimers[runId]); delete _runTimers[runId]; }
  document.getElementById('run-card-' + runId)?.remove();
  const list = document.getElementById('runs-list');
  if (!list.children.length) closeRunsPanel();
  else updateRunsFab();
}

async function sendFollowup(runId) {
  const el = document.getElementById('followup-' + runId);
  if (!el) return;
  const msg = el.value.trim();
  if (!msg) return;
  el.value = '';
  const newRunId = await pywebview.api.send_action_followup(runId, msg);
  if (newRunId) addRunCard(newRunId);
}

// ── Regenerar minutas ─────────────────────────────────────────────────────────

function toggleRegenBar(forceVisible) {
  const bar = document.getElementById('regen-bar');
  if (!bar) return;
  const show = forceVisible !== undefined ? forceVisible : !_regenVisible;
  _regenVisible = show;
  bar.classList.toggle('hidden', !show);
  if (show) document.getElementById('regen-textarea')?.focus();
}

function _regenStageLabel(stage) {
  const key = 'regen_stage_' + stage;
  return t(key) || stage;
}

function _showRegenProgress(bar) {
  bar.innerHTML = `
    <div class="regen-progress-wrap">
      <div class="regen-progress-label" id="regen-progress-label">${t('toast_regenerating')}</div>
      <div class="regen-progress-track">
        <div class="regen-progress-fill" id="regen-progress-fill" style="width:0%"></div>
      </div>
      <div class="regen-progress-pct" id="regen-progress-pct">0%</div>
    </div>`;
  bar.classList.remove('hidden');
}

function _restoreRegenBar(bar) {
  bar.classList.add('hidden');
  bar.innerHTML = `
    <textarea id="regen-textarea" rows="2" placeholder="${t('regen_placeholder')}"></textarea>
    <div class="regen-bar-btns">
      <button class="btn btn-primary btn-sm" id="btn-regen-confirm">${t('regen_confirm')}</button>
      <button class="btn btn-ghost btn-sm" id="btn-regen-cancel">${t('regen_cancel')}</button>
    </div>`;
  _regenVisible = false;
  const path = currentPath;
  document.getElementById('btn-regen-confirm')?.addEventListener('click', () => confirmRegen(path));
  document.getElementById('btn-regen-cancel')?.addEventListener('click', () => toggleRegenBar(false));
}

async function confirmRegen(path) {
  const ta = document.getElementById('regen-textarea');
  const ctx = ta ? ta.value.trim() : '';

  const bar = document.getElementById('regen-bar');
  _showRegenProgress(bar);

  const ok = await pywebview.api.regenerate_minutes(path, ctx);
  if (!ok) {
    _restoreRegenBar(bar);
    showToast(t('toast_regen_error'));
    return;
  }

  // Polling: actualiza barra de progreso cada segundo hasta done (max 120s)
  for (let i = 0; i < 120; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try {
      const s = await pywebview.api.get_regen_status(path);
      const fill  = document.getElementById('regen-progress-fill');
      const label = document.getElementById('regen-progress-label');
      const pctEl = document.getElementById('regen-progress-pct');
      if (fill)  fill.style.width  = (s.pct || 0) + '%';
      if (pctEl) pctEl.textContent = (s.pct || 0) + '%';
      if (label) label.textContent = s.error ? t('regen_stage_error') : _regenStageLabel(s.stage);

      if (s.done) {
        if (s.error) {
          _restoreRegenBar(bar);
          showToast(t('regen_stage_error') + ': ' + s.error);
          return;
        }
        // Actualizar el contenido de las notas en pantalla
        const html = await pywebview.api.get_minutes_html(path);
        if (html) {
          const sec = document.getElementById('section-notes');
          if (sec) {
            const mc = sec.querySelector('.minutes-content');
            if (mc) mc.innerHTML = sanitizeHtml(html);
          }
        }
        _restoreRegenBar(bar);
        showToast(t('toast_regen_done'));
        return;
      }
    } catch (_) {}
  }
  _restoreRegenBar(bar);
  showToast(t('toast_regen_done'));
}

// ── Resize sidebar ────────────────────────────────────────────────────────────

function initResize() {
  const handle  = document.querySelector('.resize-handle');
  const sidebar = document.querySelector('.sidebar');
  if (!handle || !sidebar) return;

  const saved = localStorage.getItem('sidebarWidth');
  if (saved) sidebar.style.width = saved + 'px';

  let isResizing = false, startX = 0, startW = 0;

  handle.addEventListener('mousedown', e => {
    isResizing = true;
    startX = e.clientX;
    startW = sidebar.offsetWidth;
    handle.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  });

  document.addEventListener('mousemove', e => {
    if (!isResizing) return;
    const w = Math.max(160, Math.min(480, startW + (e.clientX - startX)));
    sidebar.style.width = w + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    handle.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    localStorage.setItem('sidebarWidth', sidebar.offsetWidth);
  });
}

// ── Pipeline status tab + panel ───────────────────────────────────────────────

let _pipelinePanelOpen = false;

function _fmtEta(secs) {
  secs = Math.round(secs);
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60), s = secs % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}

async function updatePipelineFooter() {
  const tab  = document.getElementById('pipeline-tab');
  const dot  = document.getElementById('pipeline-tab-dot');
  const body = document.getElementById('pipeline-panel-body');
  if (!tab || !body) return;

  let status;
  try { status = await pywebview.api.get_pipeline_status(); } catch (_) { return; }

  const jobs = status?.jobs ?? [];

  if (!jobs.length) {
    tab.classList.add('idle');
    dot.className = 'pipeline-tab-dot idle';
    body.innerHTML = `<div style="color:var(--muted);font-size:12px;text-align:center;padding:20px 0">${t('pipeline_idle') || 'Sin actividad'}</div>`;
    _clearStatusView();
    return;
  }

  tab.classList.remove('idle');
  const anyRecording = jobs.some(j => j.stage === 'recording');
  dot.className = 'pipeline-tab-dot ' + (anyRecording ? 'recording' : 'processing');

  const cardsHtml = jobs.map(j => {
    // ── En cola ──────────────────────────────────────────────
    if (j.stage === 'queued') {
      return `
        <div class="pj-card pj-card--queued">
          <div class="pj-head">
            <div class="pj-eyebrow"><span class="pj-chev muted">&gt;</span><span class="pj-eyebrow-txt">${t('pipeline_queued') || 'en cola'}</span></div>
            <div class="pj-title">${escHtml(j.title || j.label)}</div>
          </div>
        </div>`;
    }

    // ── Grabando ─────────────────────────────────────────────
    if (j.stage === 'recording') {
      return `
        <div class="pj-card pj-card--recording">
          <div class="pj-head">
            <div class="pj-eyebrow"><span class="pj-rec-dot"></span><span class="pj-eyebrow-txt">REC</span></div>
            <div class="pj-title">${escHtml(j.label)}</div>
          </div>
        </div>`;
    }

    // ── Procesando: stepper con columna de flujo ─────────────
    const totalSteps = j.total_steps || 3;
    const curStep = j.step || 1;
    const curFrac = j.pct != null ? j.pct / 100 : 0.5;  // etapas indeterminadas cuentan como medio
    const overall = Math.min(100, Math.round(((curStep - 1 + curFrac) / totalSteps) * 100));

    const eyebrowBits = [];
    if (j.time) eyebrowBits.push(escHtml(j.time));
    eyebrowBits.push(`${t('nav_status') || 'En curso'}`.toUpperCase());
    const eyebrow = eyebrowBits.join(' · ');
    const titleHtml = `<div class="pj-title">${escHtml(j.title || j.label)}</div>`;

    const steps = [
      t('step_transcribing') || 'Transcribiendo',
      t('step_minutes')      || 'Generando minutas',
      t('step_actions')      || 'Generando acciones',
    ];
    const stagesHtml = steps.map((label, i) => {
      const n = i + 1;
      const isDone   = n < curStep;
      const isActive = n === curStep;
      const state = isDone ? 'done' : isActive ? 'active' : 'pending';

      let barHtml = '';
      if (isDone) {
        barHtml = `<div class="pj-bar"><div class="pj-bar-fill done" style="width:100%"></div></div>`;
      } else if (isActive && j.pct != null) {
        barHtml = `<div class="pj-bar"><div class="pj-bar-fill active" style="width:${j.pct}%"></div></div>`;
      } else if (isActive) {
        barHtml = `<div class="pj-bar"><div class="pj-bar-fill shimmer"></div></div>`;
      } else {
        barHtml = `<div class="pj-bar"></div>`;
      }
      let etaHtml = '';
      if (isActive && j.pct != null && j.pct > 3 && j.step_started) {
        const elapsed = Date.now() / 1000 - j.step_started;
        const remaining = elapsed * (100 - j.pct) / j.pct;
        if (remaining > 2 && remaining < 3600) etaHtml = `<span class="pj-stage-eta">~${_fmtEta(remaining)}</span>`;
      }
      const rightHtml = isDone
        ? `<span class="pj-stage-tick">✓</span>`
        : (isActive && j.pct != null ? `${etaHtml}<span class="pj-stage-pct">${j.pct}%</span>` : '');

      return `
        <div class="pj-stage ${state}">
          <span class="pj-chev">&gt;</span>
          <div class="pj-stage-body">
            <div class="pj-stage-row">
              <span class="pj-stage-label">${escHtml(label)}</span>
              ${rightHtml}
            </div>
            ${barHtml}
          </div>
        </div>`;
    }).join('');

    return `
      <div class="pj-card pj-card--active">
        <div class="pj-head">
          <div class="pj-eyebrow"><span class="pj-live-dot"></span><span class="pj-eyebrow-txt">${eyebrow}</span></div>
          ${titleHtml}
        </div>
        <div class="pj-flow" style="--flow: ${overall}%">
          <div class="pj-spine"><div class="pj-spine-fill" style="height:${overall}%"></div></div>
          <div class="pj-stages">${stagesHtml}</div>
        </div>
      </div>`;
  }).join('');

  body.innerHTML = cardsHtml;

  // Actualizar vista "En curso" si está abierta
  const statusBody = document.getElementById('status-view-body');
  if (statusBody) statusBody.innerHTML = cardsHtml;

  // Dot indicador en el nav
  const navDot = document.getElementById('nav-status-dot');
  if (navDot) navDot.classList.toggle('hidden', !jobs.length);
}

// Actualizar vista "En curso" cuando no hay jobs
function _clearStatusView() {
  const statusBody = document.getElementById('status-view-body');
  if (statusBody) statusBody.innerHTML =
    `<div class="status-idle">
       <div class="status-idle-mark">&gt;</div>
       <div class="status-idle-txt">${t('status_idle') || 'Sin actividad'}</div>
     </div>`;
  const navDot = document.getElementById('nav-status-dot');
  if (navDot) navDot.classList.add('hidden');
}

function togglePipelinePanel() {
  _pipelinePanelOpen = !_pipelinePanelOpen;
  const panel = document.getElementById('pipeline-panel');
  const tab   = document.getElementById('pipeline-tab');
  if (panel) panel.classList.toggle('open', _pipelinePanelOpen);
  if (tab)   tab.classList.toggle('panel-open', _pipelinePanelOpen);
}

// ── Editar notas (editor visual WYSIWYG) ──────────────────────────────────────

let _editingNotes = false;

async function toggleEditNotes(path) {
  if (_editingNotes) return;
  const sec = document.getElementById('section-notes');
  if (!sec) return;
  document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-notes')?.classList.add('active');
  document.getElementById('section-notes')?.classList.remove('hidden');
  document.getElementById('section-actions')?.classList.add('hidden');

  let html = '';
  try { html = await pywebview.api.get_minutes_html(path); } catch (_) {}
  _editingNotes = true;
  sec.innerHTML = `
    <div class="notes-edit-toolbar">
      <div class="notes-edit-tools">
        <button class="notes-tool" data-cmd="bold" title="${t('fmt_bold')}"><b>B</b></button>
        <button class="notes-tool" data-cmd="italic" title="${t('fmt_italic')}"><i>I</i></button>
        <button class="notes-tool" data-block="H2" title="${t('fmt_h2')}">H2</button>
        <button class="notes-tool" data-block="H3" title="${t('fmt_h3')}">H3</button>
        <button class="notes-tool" data-block="P" title="${t('fmt_text')}">¶</button>
        <button class="notes-tool" data-cmd="insertUnorderedList" title="${t('fmt_list')}">•</button>
        <span class="notes-tool-dropdown">
          <button class="notes-tool" data-action="tablemenu" title="${t('fmt_table')}"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 9h18M3 14h18M9 4v16M15 4v16"/></svg> ▾</button>
          <div class="table-menu hidden" id="table-menu">
            <button data-tbl="insert">${t('tbl_insert')}</button>
            <button data-tbl="addrow">${t('tbl_addrow')}</button>
            <button data-tbl="delrow">${t('tbl_delrow')}</button>
            <button data-tbl="addcol">${t('tbl_addcol')}</button>
            <button data-tbl="delcol">${t('tbl_delcol')}</button>
            <button data-tbl="deltable" class="table-menu-danger">${t('tbl_delete')}</button>
          </div>
        </span>
      </div>
      <div class="notes-edit-btns">
        <button class="btn btn-primary btn-sm" id="btn-notes-save">${t('save_btn')}</button>
        <button class="btn btn-ghost btn-sm" id="btn-notes-cancel">${t('cancel')}</button>
      </div>
    </div>
    <div class="notes-edit-hint">${t('edit_notes_hint')}</div>
    <div class="notes-edit-area minutes-content" id="notes-edit-area" contenteditable="true">${html ? sanitizeHtml(html) : ''}</div>`;
  const area = document.getElementById('notes-edit-area');
  if (area) area.focus();
  const _tb = sec.querySelector('.notes-edit-toolbar');
  const _hdr = document.querySelector('.detail-header');
  const _tabs = document.querySelector('.detail-tabs');
  if (_tb) _tb.style.top = ((_hdr?.offsetHeight || 0) + (_tabs?.offsetHeight || 0)) + 'px';
  sec.querySelectorAll('.notes-tool').forEach(btn => {
    btn.addEventListener('mousedown', e => e.preventDefault());
    btn.addEventListener('click', () => {
      if (btn.dataset.action === 'tablemenu') {
        document.getElementById('table-menu')?.classList.toggle('hidden');
        return;
      }
      area.focus();
      if (btn.dataset.cmd) document.execCommand(btn.dataset.cmd, false, null);
      else if (btn.dataset.block) document.execCommand('formatBlock', false, btn.dataset.block);
    });
  });
  sec.querySelectorAll('#table-menu button').forEach(mi => {
    mi.addEventListener('mousedown', e => e.preventDefault());
    mi.addEventListener('click', () => {
      _tableOp(area, mi.dataset.tbl);
      document.getElementById('table-menu')?.classList.add('hidden');
    });
  });
  document.getElementById('btn-notes-save').onclick = async () => {
    const md = htmlToMarkdown(area);
    let ok = false;
    try { ok = await pywebview.api.save_minutes_notes(path, md); } catch (_) {}
    _editingNotes = false;
    if (ok) showToast(t('notes_saved'));
    await _reRenderNotes(path);
  };
  document.getElementById('btn-notes-cancel').onclick = async () => {
    _editingNotes = false;
    await _reRenderNotes(path);
  };
}

function htmlToMarkdown(root) {
  function inline(node) {
    let out = '';
    node.childNodes.forEach(n => {
      if (n.nodeType === 3) { out += n.textContent; return; }
      if (n.nodeType !== 1) return;
      const tag = n.tagName.toLowerCase();
      const inner = inline(n);
      if (tag === 'strong' || tag === 'b') out += `**${inner}**`;
      else if (tag === 'em' || tag === 'i') out += `*${inner}*`;
      else if (tag === 'code') out += '`' + inner + '`';
      else if (tag === 'a') out += `[${inner}](${n.getAttribute('href') || ''})`;
      else if (tag === 'br') out += '\n';
      else out += inner;
    });
    return out;
  }
  function tableToMarkdown(table) {
    const trs = [...table.querySelectorAll('tr')];
    const out = [];
    trs.forEach((tr, ri) => {
      const cells = [...tr.children].map(c => (inline(c).trim().replace(/\|/g, '\\|')) || ' ');
      out.push('| ' + cells.join(' | ') + ' |');
      if (ri === 0) out.push('| ' + cells.map(() => '---').join(' | ') + ' |');
    });
    return out;
  }
  const lines = [];
  function block(node) {
    node.childNodes.forEach(n => {
      if (n.nodeType === 3) { const txt = n.textContent.trim(); if (txt) lines.push(txt, ''); return; }
      if (n.nodeType !== 1) return;
      const tag = n.tagName.toLowerCase();
      if (tag === 'h1') lines.push('# ' + inline(n).trim(), '');
      else if (tag === 'h2') lines.push('## ' + inline(n).trim(), '');
      else if (tag === 'h3') lines.push('### ' + inline(n).trim(), '');
      else if (tag === 'p' || tag === 'div') { const txt = inline(n).trim(); if (txt) lines.push(txt, ''); else block(n); }
      else if (tag === 'ul') { n.querySelectorAll(':scope > li').forEach(li => lines.push('- ' + inline(li).trim())); lines.push(''); }
      else if (tag === 'ol') { let i = 1; n.querySelectorAll(':scope > li').forEach(li => lines.push((i++) + '. ' + inline(li).trim())); lines.push(''); }
      else if (tag === 'table') { tableToMarkdown(n).forEach(l => lines.push(l)); lines.push(''); }
      else if (tag === 'blockquote') { lines.push('> ' + inline(n).trim(), ''); }
      else if (tag === 'br') { lines.push(''); }
      else { const txt = inline(n).trim(); if (txt) lines.push(txt, ''); }
    });
  }
  block(root);
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

function _placeCaret(node) {
  try {
    const sel = window.getSelection();
    const r = document.createRange();
    r.setStart(node, 0); r.collapse(true);
    sel.removeAllRanges(); sel.addRange(r);
  } catch (_) {}
}

function _tableCtx(area) {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return null;
  let node = sel.anchorNode, cell = null, tr = null, table = null;
  while (node && node !== area) {
    if (node.nodeType === 1) {
      const tag = node.tagName;
      if (!cell && (tag === 'TD' || tag === 'TH')) cell = node;
      if (!tr && tag === 'TR') tr = node;
      if (tag === 'TABLE') { table = node; break; }
    }
    node = node.parentNode;
  }
  if (!table) return null;
  if (!tr && cell) tr = cell.parentNode;
  const cellIndex = (cell && tr) ? [...tr.children].indexOf(cell) : 0;
  return { table, tr, cell, cellIndex };
}

function _insertTable(area) {
  area.focus();
  const cols = 3, rows = 2;
  let html = '<table>';
  for (let r = 0; r < rows; r++) {
    html += '<tr>';
    for (let c = 0; c < cols; c++) {
      const tag = r === 0 ? 'th' : 'td';
      html += `<${tag}>${r === 0 ? 'Columna ' + (c + 1) : '&nbsp;'}</${tag}>`;
    }
    html += '</tr>';
  }
  html += '</table><p><br></p>';
  document.execCommand('insertHTML', false, html);
}

function _tableOp(area, op) {
  area.focus();
  if (op === 'insert') { _insertTable(area); return; }
  const ctx = _tableCtx(area);
  if (!ctx) { showToast(t('table_need_cursor')); return; }
  const { table, tr, cellIndex } = ctx;
  const rows = [...table.querySelectorAll('tr')];
  if (op === 'addrow') {
    const cols = (tr || rows[0]).children.length || 1;
    const nr = document.createElement('tr');
    for (let i = 0; i < cols; i++) { const td = document.createElement('td'); td.innerHTML = '<br>'; nr.appendChild(td); }
    (tr || rows[rows.length - 1]).after(nr);
    _placeCaret(nr.firstChild);
  } else if (op === 'delrow') {
    if (rows.length <= 1) { table.remove(); return; }
    (tr || rows[rows.length - 1]).remove();
  } else if (op === 'addcol') {
    rows.forEach(r => {
      const isHead = !!r.querySelector('th') && !r.querySelector('td');
      const cell = document.createElement(isHead ? 'th' : 'td');
      cell.innerHTML = isHead ? 'Columna' : '<br>';
      const ref = r.children[cellIndex];
      if (ref && ref.nextSibling) r.insertBefore(cell, ref.nextSibling);
      else r.appendChild(cell);
    });
  } else if (op === 'delcol') {
    const colCount = rows[0] ? rows[0].children.length : 0;
    if (colCount <= 1) { table.remove(); return; }
    rows.forEach(r => { const c = r.children[cellIndex]; if (c) c.remove(); });
  } else if (op === 'deltable') {
    table.remove();
  }
}

async function _reRenderNotes(path) {
  const sec = document.getElementById('section-notes');
  if (!sec) return;
  let html = '';
  try { html = await pywebview.api.get_minutes_html(path); } catch (_) {}
  sec.innerHTML = `<div class="minutes-content">${html ? sanitizeHtml(html) : `<em>${t('no_minutes')}</em>`}</div>`;
}
