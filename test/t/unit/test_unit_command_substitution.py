import pytest

from conftest import assert_bash_exec, assert_complete


@pytest.mark.bashcomp(
    cmd=None,
    ignore_env=r"^[+-](COMPREPLY|REPLY)=",
)
class TestUnitCommandSubstitution:
    """Test completion inside $() command substitutions."""

    wordlist = ["alpha", "bravo"]
    later_wordlist = ["delta", "gamma"]

    @pytest.fixture(params=["simple", "prev_sensitive"], scope="class")
    def functions(self, bash, request):
        if request.param == "simple":
            assert_bash_exec(
                bash,
                "_csub_compfunc() {"
                '  COMPREPLY=($(compgen -W "%s"'
                ' -- "${COMP_WORDS[COMP_CWORD]}"));'
                "}; "
                "complete -F _csub_compfunc csub_cmd"
                % " ".join(self.wordlist),
            )
        else:
            # prev-sensitive: returns wordlist when prev is the command
            # name (first-arg position), later_wordlist otherwise.
            assert_bash_exec(
                bash,
                "_csub_compfunc() {"
                " local c=${COMP_WORDS[COMP_CWORD]}"
                " p=${COMP_WORDS[COMP_CWORD-1]};"
                ' local w="%s"; [[ $p != csub_cmd ]] && w="%s";'
                ' COMPREPLY=($(compgen -W "$w" -- "$c")); }'
                % (" ".join(self.wordlist), " ".join(self.later_wordlist)),
            )
            assert_bash_exec(bash, "complete -F _csub_compfunc csub_cmd")
        assert_bash_exec(bash, "_csub_uniqcmd() { :; }")
        return request.param

    def test_closed_substitution(self, bash, functions):
        assert assert_complete(
            bash, "echo $(echo hi) ", cwd="shared/default"
        ) == ["bar", "bar bar.d/", "foo", "foo.d/"]

    def test_single_level(self, bash, functions):
        assert assert_complete(bash, "echo $(csub_cmd ") == self.wordlist

    def test_single_level_partial(self, bash, functions):
        assert assert_complete(bash, "echo $(csub_cmd a") == ["lpha"]

    def test_empty_substitution(self, bash, functions):
        """An empty $( offers nothing."""
        assert assert_complete(bash, "echo $(") == []

    def test_blank_substitution(self, bash, functions):
        """A $( holding only whitespace offers nothing."""
        assert assert_complete(bash, "echo $(   ") == []

    def test_command_name(self, bash, functions):
        """The first word inside $( completes as a command name."""
        assert assert_complete(bash, "echo $(_csub_uniqc") == ["md"]

    def test_cursor_before_closing_paren(self, bash, functions):
        """Text after the cursor, including a closing ), is not scanned."""
        assert (
            assert_complete(bash, "echo $(csub_cmd ", trail=")")
            == self.wordlist
        )

    def test_nested(self, bash, functions):
        assert (
            assert_complete(bash, "echo $(echo foo $(csub_cmd ")
            == self.wordlist
        )

    def test_nested_partial(self, bash, functions):
        assert assert_complete(bash, "echo $(echo foo $(csub_cmd b") == [
            "ravo"
        ]

    def test_closed_then_open(self, bash, functions):
        assert (
            assert_complete(bash, "echo $(echo hi) $(csub_cmd ")
            == self.wordlist
        )

    def test_open_then_closed(self, bash, functions):
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd $(echo hi) ") == expected

    def test_closed_mid_word_then_open(self, bash, functions):
        """$( appears mid-word after a closed substitution."""
        assert (
            assert_complete(bash, "echo a$(echo x)b$(csub_cmd ")
            == self.wordlist
        )

    def test_closed_path_then_open(self, bash, functions):
        """Closed $() separated by / from a new open $(."""
        assert (
            assert_complete(bash, "echo $(echo x)/$(csub_cmd ")
            == self.wordlist
        )

    def test_closed_mid_word_then_open_partial(self, bash, functions):
        """Partial completion after a closed-then-open mid-word."""
        assert assert_complete(bash, "echo a$(echo x)b$(csub_cmd a") == [
            "lpha"
        ]

    def test_deeply_nested(self, bash, functions):
        """Three levels of unclosed $(."""
        assert (
            assert_complete(bash, "echo $(a $(b $(csub_cmd ") == self.wordlist
        )

    def test_multiple_closed_before_open(self, bash, functions):
        """Multiple closed substitutions before an unclosed one."""
        assert (
            assert_complete(bash, "echo $(echo a) $(echo b) $(csub_cmd ")
            == self.wordlist
        )

    def test_dquote_outer_context(self, bash, functions):
        """$() inside an outer double-quoted string completes the inner command.

        In echo "$(csub_cmd <TAB>, the outer " opens a double-quoted context
        but $( still starts a command substitution.  The scanner must recognise
        $( even while in_quote == '"' and reset quote state for the interior.
        """
        assert assert_complete(bash, 'echo "$(csub_cmd ') == self.wordlist

    def test_dquote_with_nested_csub_containing_semicolon(
        self, bash, functions
    ):
        """Semicolon inside a closed $() within double quotes is not a separator.

        In echo $(csub_cmd "$(sub "x; y")" , the inner scanner walks
        inner_line = csub_cmd "$(sub "x; y")" .  The $( inside "..." should
        reset the quote context (as the outer scanner does), so the ; between
        the " pair inside the substitution stays quoted.  Without the reset,
        the first " inside $(sub ...) prematurely closes _inner_in_quote,
        exposing ; as a command separator at depth 0.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert (
            assert_complete(bash, 'echo $(csub_cmd "$(sub "x; y")" ')
            == expected
        )

    def test_quoted_paren(self, bash, functions):
        """Paren inside quotes incorrectly closes the substitution."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, 'echo $(csub_cmd ")" ') == expected

    def test_escaped_paren(self, bash, functions):
        """Escaped paren incorrectly closes the substitution."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd \\) ") == expected

    def test_escaped_quote_in_double_quotes(self, bash, functions):
        r"""Backslash-escaped \" inside double quotes must not break scanner.

        In "\")", the \" is a literal quote and ) is still inside the
        double-quoted string.  If the scanner fails to consume the
        backslash before checking quote state, the \" toggles the quote
        off and the ) incorrectly closes the $(.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, 'echo $(csub_cmd "\\")" ') == expected

    def test_ansi_c_quote_containing_paren(self, bash, functions):
        r"""Paren inside $'...' does not close the substitution.

        In $'\')', the \' is an escaped quote within ANSI-C quoting, so
        the ) that follows is still inside the string.  A scanner that
        treats backslash as literal there, as it is in plain single
        quotes, reads \' as closing the quote and the ) as closing the
        $(, and falls through to command-name completion.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd $'\\')' ") == expected

    def test_backtick_containing_paren(self, bash, functions):
        """Paren inside a closed backtick substitution does not close the $(.

        Bash keeps the $( open across a complete `...` pair, so the )
        inside it belongs to that substitution, not to the enclosing $(.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd `echo )` ") == expected

    def test_backtick_in_double_quotes(self, bash, functions):
        """Double-quote context is restored after a backtick pair closes.

        In "`echo )` )" the second ) is still inside the double quotes.
        If closing the backtick pair dropped the saved quote state, that
        ) would be read as closing the $(.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert (
            assert_complete(bash, 'echo $(csub_cmd "`echo )` )" ') == expected
        )

    @pytest.mark.xfail(
        reason="an unclosed ` is not a command boundary, unlike at the "
        "top level"
    )
    def test_unclosed_backtick(self, bash, functions):
        """Bash treats ` as a command separator, so at the top level
        "csub_cmd `echo " completes for echo.  Inside $( the rest of the
        line is swallowed and csub_cmd keeps the completion."""
        assert assert_complete(
            bash, "echo $(csub_cmd `echo ", cwd="shared/default"
        ) == ["bar", "bar bar.d/", "foo", "foo.d/"]

    def test_subshell(self, bash, functions):
        """Inner subshell paren incorrectly closes the substitution."""
        assert (
            assert_complete(bash, "echo $( (subshell) csub_cmd ")
            == self.wordlist
        )

    def test_time_prefix(self, bash, functions):
        """A command-prefix word such as time hands over to its command.

        The completion for time re-dispatches to the command it
        prefixes, so it composes with the $( re-dispatch.
        """
        assert assert_complete(bash, "echo $( time csub_cmd ") == self.wordlist

    def test_arithmetic(self, bash, functions):
        """Arithmetic expansion paren incorrectly closes the substitution."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd $(( 1+1 )) ") == expected

    def test_arithmetic_command(self, bash, functions):
        """Arithmetic command paren incorrectly closes the substitution."""
        assert (
            assert_complete(bash, "echo $( (( x++ )); csub_cmd ")
            == self.wordlist
        )

    def test_brace_group(self, bash, functions):
        """A { opening a brace group is a command boundary.

        Bash's own completion lists { among its command separators, so
        "{ csub_cmd " completes csub_cmd's arguments at the top level.
        Inside $( the inner scanner must do the same rather than take
        { as the command name.
        """
        assert assert_complete(bash, "echo $( { csub_cmd ") == self.wordlist

    def test_brace_expansion_mid_word(self, bash, functions):
        """A { inside a word is brace expansion, not a command boundary."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd a{b,c} ") == expected

    def test_process_substitution(self, bash, functions):
        """Process substitution paren does not close the substitution."""
        assert assert_complete(
            bash, "echo $( cat <(ls) csub_cmd ", cwd="shared/default"
        ) == ["bar", "bar bar.d/", "foo", "foo.d/"]

    def test_extglob(self, bash, functions):
        """Extended glob paren does not close the substitution."""
        assert assert_complete(
            bash,
            "echo $( ls @(file1|file2) csub_cmd ",
            shopt={"extglob": True},
            cwd="shared/default",
        ) == ["bar", "bar bar.d/", "foo", "foo.d/"]

    def test_case_pattern(self, bash, functions):
        """Case pattern paren does not close the substitution."""
        assert assert_complete(
            bash,
            "echo $( case $x in (y) csub_cmd ",
            cwd="shared/default",
        ) == ["bar", "bar bar.d/", "foo", "foo.d/"]

    def test_pipe(self, bash, functions):
        """A | starts a new simple command."""
        assert assert_complete(bash, "echo $(a | csub_cmd ") == self.wordlist

    def test_pipe_stderr(self, bash, functions):
        """A |& starts a new simple command."""
        assert assert_complete(bash, "echo $(a |& csub_cmd ") == self.wordlist

    def test_or_list(self, bash, functions):
        """A || starts a new simple command."""
        assert assert_complete(bash, "echo $(a || csub_cmd ") == self.wordlist

    def test_and_list(self, bash, functions):
        """A && starts a new simple command."""
        assert assert_complete(bash, "echo $(a && csub_cmd ") == self.wordlist

    def test_background(self, bash, functions):
        """A single & starts a new simple command."""
        assert assert_complete(bash, "echo $(a & csub_cmd ") == self.wordlist

    def test_separator_in_quotes(self, bash, functions):
        """A separator inside quotes is not a command boundary."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, 'echo $(csub_cmd "a | b" ') == expected

    def test_redirect_noclobber(self, bash, functions):
        """The | of >| is a redirection, not a separator.

        Bash's own completion special-cases >| at the top level, so the
        inner scanner must match it.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert (
            assert_complete(bash, "echo $(csub_cmd >| /dev/null ") == expected
        )

    def test_redirect_dup(self, bash, functions):
        """The & of 2>&1 is a redirection, not a separator.

        Bash's own completion gets this wrong at the top level, where
        "cmd 2>&1 " completes command names.  Inside $( the scanner
        recognises the operator, so the enclosing command keeps the
        completion.
        """
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd 2>&1 ") == expected

    def test_redirect_all(self, bash, functions):
        """The & of &> is a redirection, not a separator."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert (
            assert_complete(bash, "echo $(csub_cmd &>/dev/null ") == expected
        )

    def test_redirect_input_dup(self, bash, functions):
        """The & of <& is a redirection, not a separator."""
        expected = (
            self.wordlist if functions == "simple" else self.later_wordlist
        )
        assert assert_complete(bash, "echo $(csub_cmd <&0 ") == expected

    @pytest.mark.xfail(
        reason="a redirection before the command word hides it, as at "
        "the top level"
    )
    def test_redirection_before_command(self, bash, functions):
        assert (
            assert_complete(bash, "echo $( >/dev/null csub_cmd ")
            == self.wordlist
        )

    @pytest.mark.xfail(
        reason="! is not a command boundary, as at the top level"
    )
    def test_bang_prefix(self, bash, functions):
        assert assert_complete(bash, "echo $( ! csub_cmd ") == self.wordlist

    # Not tested: scanner is not comment-aware.
    # A # comment containing ) would incorrectly close the $(.  However,
    # # extends to end of line with no closing delimiter, so anything
    # after # on the same line is dead (including TAB).  The only way a
    # comment containing ) could precede completable text is multi-line
    # input (newline after comment, then new command text), which the
    # assert_complete harness doesn't support (it expects single-line
    # input; multi-line requires handling PS2 continuation prompts).
    # Purely theoretical for interactive use.


@pytest.mark.bashcomp(
    cmd=None,
    ignore_env=r"^[+-](COMPREPLY|REPLY)=",
)
class TestCsubPrevWordBoundary:
    """Test COMP_WORDS word boundaries via a prev-reporting function."""

    @pytest.fixture(scope="class")
    def functions(self, bash):
        assert_bash_exec(
            bash,
            "_csub_report_prev() {"
            '  COMPREPLY=("${COMP_WORDS[COMP_CWORD-1]}");'
            "}; "
            "complete -F _csub_report_prev csub_report_cmd",
        )

    def test_prev_first_arg(self, bash, functions):
        assert assert_complete(bash, "echo $(csub_report_cmd ") == [
            "csub_report_cmd"
        ]

    def test_prev_second_arg(self, bash, functions):
        assert assert_complete(bash, "echo $(csub_report_cmd x ") == ["x"]

    @pytest.mark.xfail(
        reason="IFS splitting breaks quoted multi-word arguments"
    )
    def test_prev_after_quoted_spaces(self, bash, functions):
        """COMP_WORDS is built by IFS splitting, which is not quote-aware.

        With the quoted argument "a b", prev should be the full quoted
        string, but IFS splitting produces separate "a and b" words,
        leaving b" as prev instead.
        """
        assert assert_complete(bash, 'echo $(csub_report_cmd "a b" ') == [
            '"a b"'
        ]
