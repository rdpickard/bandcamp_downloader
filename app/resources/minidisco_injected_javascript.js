var minidisco_ui_account_username = null;
var minidisco_ui_account_password = null;

function minidisco_ui_script_hook_init() {
    console.log("minidisco_ui_script_hook_init called")
    minidisco_ui_account_username = null;
    minidisco_ui_account_password = null;
}

function minidisco_ui_script_hook_set_username_and_password(account_username_from_script, account_password_from_script ) {
    console.log("minidisco_ui_script_hook_set_username_and_password called with "+account_username_from_script+" "+account_password_from_script)
    minidisco_ui_account_username = account_username_from_script;
    minidisco_ui_account_password = account_password_from_script;
}

function minidisco_ui_script_hook_loginpage_welcome_modal() {
    if (minidisco_ui_account_password == null || minidisco_ui_account_username == null) {
        $('#welcome_modal_no_account_info').modal('show');
    } else {
        $('#welcome_modal_with_account_info').modal('show');
    }
}

$('#welcome_modal_with_account_info').modal({
    onApprove: function () {
        console.log("login modal approved")
        var minidisco_flow_step_1_element = document.createElement('input');
        minidisco_flow_step_1_element.setAttribute("id", "minidisco_flow_step_1");
        minidisco_flow_step_1_element.value="approved"
        document.querySelector('body').appendChild(minidisco_flow_step_1_element);
    },
    onDeny: function () {
        console.log("login modal denied")
        var minidisco_flow_step_1_element = document.createElement('input');
        minidisco_flow_step_1_element.setAttribute("id", "minidisco_flow_step_1");
        minidisco_flow_step_1_element.value="quit"
        document.querySelector('body').appendChild(minidisco_flow_step_1_element);
    },
})

$('#welcome_modal_no_account_info').modal({
    onApprove: function () {
        console.log("login modal approved")
        var minidisco_flow_step_1_element = document.createElement('input');
        minidisco_flow_step_1_element.setAttribute("id", "minidisco_flow_step_1");
        minidisco_flow_step_1_element.value="manual login"
        document.querySelector('body').appendChild(minidisco_flow_step_1_element);
    },
    onDeny: function () {
        console.log("login modal denied")
        var minidisco_flow_step_1_element = document.createElement('input');
        minidisco_flow_step_1_element.setAttribute("id", "minidisco_flow_step_1");
        minidisco_flow_step_1_element.value="quit"
        document.querySelector('body').appendChild(minidisco_flow_step_1_element);
    },
})

function append_to_blorp(new_stuff) {
    $("#blorp").append(new_stuff)
}
