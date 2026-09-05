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
