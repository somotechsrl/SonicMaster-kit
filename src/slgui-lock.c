/* TSMA performance UI: hide/disable the menu bar and its accelerator groups.
 * Loaded only into slgui through GTK_MODULES. No audio/MIDI interception. */
typedef unsigned long GType;
typedef int gboolean;
typedef struct List {void *data;struct List *next,*prev;} List;
extern GType gtk_menu_bar_get_type(void);
extern GType gtk_container_get_type(void);
extern int g_type_check_instance_is_a(void*,GType);
extern List *gtk_container_get_children(void*);
extern List *gtk_window_list_toplevels(void);
extern List *gtk_accel_groups_from_object(void*);
extern void gtk_window_remove_accel_group(void*,void*);
extern void gtk_widget_hide(void*);
extern void gtk_widget_set_sensitive(void*,int);
extern void gtk_widget_set_no_show_all(void*,int);
extern void g_list_free(List*);
extern unsigned int g_timeout_add(unsigned int,gboolean(*)(void*),void*);
static void visit(void *widget){
 if(g_type_check_instance_is_a(widget,gtk_menu_bar_get_type())){
  gtk_widget_set_sensitive(widget,0);gtk_widget_set_no_show_all(widget,1);gtk_widget_hide(widget);return;
 }
 if(g_type_check_instance_is_a(widget,gtk_container_get_type())){
  List *children=gtk_container_get_children(widget);
  for(List *it=children;it;it=it->next)visit(it->data);
  g_list_free(children);
 }
}
static gboolean protect(void *unused){
 (void)unused;List *windows=gtk_window_list_toplevels();
 for(List *it=windows;it;it=it->next){
  void *window=it->data;visit(window);
  /* Removing groups can mutate the borrowed list, always start again. */
  List *groups;
  while((groups=gtk_accel_groups_from_object(window)))gtk_window_remove_accel_group(window,groups->data);
 }
 g_list_free(windows);return 1;
}
void gtk_module_init(int *argc,char ***argv){(void)argc;(void)argv;g_timeout_add(100,protect,0);}
